"""End-to-end round-trip: PLC simulator PUBs -> live_simulator subscribes
in PLC-driven mode -> signal chunks + LiveDcUpdate appear on the signal
PUB port. Everything runs on ephemeral TCP ports so parallel test runs
don't clash.

Because ZMQ PUB/SUB has a slow-joiner problem (a subscriber may miss
messages sent before it connected), the test uses a short warm-up
sleep plus asserts the eventual set of message types received.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import zmq

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_SIM = REPO_ROOT / "web-backend" / "scripts" / "live_simulator.py"
PLC_SIM = REPO_ROOT / "web-backend" / "scripts" / "plc_simulator.py"


def _spawn(script: Path, env: dict[str, str]) -> subprocess.Popen:
    merged_env = os.environ.copy()
    merged_env.update(env)
    return subprocess.Popen(
        [sys.executable, str(script)],
        env=merged_env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


class PlcDrivenLiveSimulatorTests:
    def test_plc_driven_mode_gates_chunks_and_emits_dc(self):
        # Ephemeral ports so we don't collide with other test runs or
        # the operator's local daemon.
        signal_url = "tcp://127.0.0.1:15570"
        plc_url = "tcp://127.0.0.1:15571"

        plc = _spawn(PLC_SIM, {"NVH_PLC_PUB_URL": plc_url, "NVH_PLC_SPEED": "0.15"})
        # SUB before spawning the producer so slow-joiner is minimized.
        ctx = zmq.Context.instance()
        sub = ctx.socket(zmq.SUB)
        sub.connect(signal_url)
        sub.setsockopt_string(zmq.SUBSCRIBE, "")

        sim = _spawn(LIVE_SIM, {
            "NVH_LIVE_PUB_URL": signal_url,
            "NVH_PLC_PUB_URL": plc_url,
        })

        # Give both processes a chance to bind + connect.
        time.sleep(0.5)

        types_seen: set[str] = set()
        deadline = time.time() + 8.0
        try:
            while time.time() < deadline:
                if sub.poll(timeout=200):
                    payload = sub.recv_string()
                    parsed = json.loads(payload)
                    types_seen.add(parsed["type"])
                if {"test_run", "signal_chunk", "dc"}.issubset(types_seen):
                    break
        finally:
            sub.close(linger=0)
            sim.terminate()
            plc.terminate()
            sim.wait(timeout=5)
            plc.wait(timeout=5)

        # We should see: RUN_STARTED (test_run RUNNING), some signal
        # chunks while log_active, and a dc event on the
        # FINAL_LOG_REQUESTED transition.
        assert "test_run" in types_seen, f"missing test_run; saw {types_seen}"
        assert "signal_chunk" in types_seen, f"missing signal_chunk; saw {types_seen}"
        assert "dc" in types_seen, f"missing dc; saw {types_seen}"


@pytest.mark.parametrize("no_plc_env", [{"NVH_PLC_PUB_URL": ""}])
class AutoModeSmokeTests:
    """When --plc-url is not set, live_simulator keeps the old
    canned-scenarios behaviour so pre-Phase-F demos still work."""

    def test_auto_mode_emits_signal_chunks_without_plc(self, no_plc_env):
        signal_url = "tcp://127.0.0.1:15572"

        ctx = zmq.Context.instance()
        sub = ctx.socket(zmq.SUB)
        sub.connect(signal_url)
        sub.setsockopt_string(zmq.SUBSCRIBE, "")

        sim_env = {"NVH_LIVE_PUB_URL": signal_url, **no_plc_env}
        sim = _spawn(LIVE_SIM, sim_env)

        time.sleep(0.5)
        types_seen: set[str] = set()
        deadline = time.time() + 6.0
        try:
            while time.time() < deadline:
                if sub.poll(timeout=200):
                    types_seen.add(json.loads(sub.recv_string())["type"])
                if "signal_chunk" in types_seen:
                    break
        finally:
            sub.close(linger=0)
            sim.terminate()
            sim.wait(timeout=5)

        assert "signal_chunk" in types_seen
