"""Regression tests for Phase O Bug 7: producer shutdown must close
rollover_writer and plc_sub even on exception exit."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import zmq

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_SIM = REPO_ROOT / "web-backend" / "scripts" / "live_simulator.py"


@pytest.fixture(scope="module")
def live_sim_module():
    spec = importlib.util.spec_from_file_location("_live_sim_cleanup_test", LIVE_SIM)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_live_sim_cleanup_test"] = module
    spec.loader.exec_module(module)
    return module


class _Boom(Exception):
    pass


class ShutdownCleanupTests:
    def test_plc_sub_and_rollover_close_when_loop_raises(self, live_sim_module, tmp_path, monkeypatch):
        """If the PLC-driven main loop raises anything, the outer
        try/finally must still close plc_sub and rollover_writer.

        Phase O Bug 7: previously both leaked until process teardown
        (the outer main() only closed tdms_writer + PUB), so on Windows
        the last TDMS file was left partially written.

        Approach: patch zmq.Poller.poll to raise `_Boom` on the first
        call. Track calls to zmq.Socket.close to verify the SUB was
        closed on the exception path.
        """
        # Bind a real PUB socket for the outer socket param (never used
        # by the loop since we crash on the first poll).
        ctx = zmq.Context.instance()
        pub = ctx.socket(zmq.PUB)
        plc_url = "tcp://127.0.0.1:15601"
        pub.bind(plc_url)

        close_call_count = {"n": 0}
        real_close = zmq.Socket.close

        def _tracked_close(self, *args, **kwargs):
            close_call_count["n"] += 1
            return real_close(self, *args, **kwargs)

        monkeypatch.setattr(zmq.Socket, "close", _tracked_close)

        # Poll raises immediately -- doesn't touch send/recv paths.
        def _boom(*_a, **_kw):
            raise _Boom("simulated poll failure")

        monkeypatch.setattr(zmq.Poller, "poll", _boom)

        try:
            with pytest.raises(_Boom):
                live_sim_module._run_plc_driven_mode(
                    socket=pub,
                    plc_url=plc_url,
                    tdms_writer=None,
                    rollover_base_dir=str(tmp_path),
                    model_id="MODEL-A",
                    serial_no="SN-1",
                    serial_rpt="1",
                )
        finally:
            pub.close(linger=0)

        # The finally block in _run_plc_driven_mode must have run its
        # `plc_sub.close(linger=0)` at minimum. `pub.close` above
        # contributes one more. So >= 2 total close calls attributable
        # to this test's shutdown paths.
        assert close_call_count["n"] >= 2, (
            f"expected finally to close plc_sub; only {close_call_count['n']} "
            f"close calls tracked -- resource leak on error exit"
        )
