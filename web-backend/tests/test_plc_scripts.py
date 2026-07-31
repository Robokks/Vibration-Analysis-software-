"""Smoke checks for the PLC producer scripts. Neither requires an
actual PLC or `python-snap7` -- we exercise --help, error paths, and
the DB decoder directly."""

from __future__ import annotations

import importlib
import importlib.util
import struct
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLC_SIM = REPO_ROOT / "web-backend" / "scripts" / "plc_simulator.py"
PLC_CLIENT = REPO_ROOT / "web-backend" / "scripts" / "plc_client.py"


class PlcSimulatorScriptTests:
    def test_help_advertises_flags(self):
        result = subprocess.run(
            [sys.executable, str(PLC_SIM), "--help"],
            capture_output=True, text=True, check=True,
        )
        assert "--pub-url" in result.stdout
        assert "--speed" in result.stdout
        assert "--once" in result.stdout


class PlcClientScriptTests:
    def test_help_advertises_expected_flags(self):
        result = subprocess.run(
            [sys.executable, str(PLC_CLIENT), "--help"],
            capture_output=True, text=True, check=True,
        )
        assert "--plc-ip" in result.stdout
        assert "--rack" in result.stdout
        assert "--slot" in result.stdout
        assert "--db-number" in result.stdout
        assert "--poll-hz" in result.stdout

    def test_clear_message_when_snap7_missing(self):
        if importlib.util.find_spec("snap7") is not None:
            pytest.skip("python-snap7 is installed -- error-path test doesn't apply")
        result = subprocess.run(
            [sys.executable, str(PLC_CLIENT), "--plc-ip", "127.0.0.1"],
            capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "python-snap7" in result.stderr
        assert "requirements-plc.txt" in result.stderr


class PlcClientDecodeTests:
    def _decode(self, buf: bytes):
        spec = importlib.util.spec_from_file_location("plc_client_mod", PLC_CLIENT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module._decode_db(buf)

    def test_decodes_start_gear_r_runup(self):
        # cmd=START, gear_id=1 (R), nvh_id=0 (RU), no trigger.
        buf = bytes([1, 1]) + struct.pack(">h", 0) + bytes([0])
        event = self._decode(buf)
        assert event.nvh_cmd == "START"
        assert event.gear_id == 1
        assert event.nvh_id == 0
        assert event.final_log_trigger is False

    def test_decodes_minus_one_sentinel(self):
        buf = bytes([0, 0]) + struct.pack(">h", -1) + bytes([0])
        assert self._decode(buf).nvh_id == -1

    def test_decodes_final_trigger(self):
        buf = bytes([1, 1]) + struct.pack(">h", 3) + bytes([1])
        event = self._decode(buf)
        assert event.final_log_trigger is True
        assert event.nvh_id == 3


class PlcSimulatorSequenceTests:
    def test_sequence_contains_all_transition_kinds(self):
        spec = importlib.util.spec_from_file_location("plc_sim_mod", PLC_SIM)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cmds = {row[0] for row in module.SCRIPTED_SEQUENCE}
        nvh_ids = {row[2] for row in module.SCRIPTED_SEQUENCE}
        assert "START" in cmds and "STOP" in cmds and "IDLE" in cmds
        assert -1 in nvh_ids and 0 in nvh_ids
        assert any(row[3] for row in module.SCRIPTED_SEQUENCE), "final trigger should fire at least once"
