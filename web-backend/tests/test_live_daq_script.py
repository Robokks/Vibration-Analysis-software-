"""The nidaqmx package is optional (only installed when the user runs
`pip install -r requirements-daq.txt` on a machine with the NI-DAQmx
driver present). This test set covers the pieces of `live_daq.py` we
can exercise without either the package or a real device."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_DAQ = REPO_ROOT / "web-backend" / "scripts" / "live_daq.py"


class LiveDaqScriptTests:
    def test_script_exists_and_is_executable(self):
        assert LIVE_DAQ.exists()
        assert LIVE_DAQ.read_text().lstrip().startswith('"""')

    def test_help_flag_lists_expected_args(self):
        result = subprocess.run(
            [sys.executable, str(LIVE_DAQ), "--help"],
            capture_output=True, text=True, check=True,
        )
        assert "--device" in result.stdout
        assert "--channel" in result.stdout
        assert "--sample-rate" in result.stdout
        assert "--pub-url" in result.stdout

    def test_clear_message_when_nidaqmx_missing(self):
        # If nidaqmx *is* installed (rare in CI, common on a NI workstation),
        # the import succeeds and this test doesn't apply.
        try:
            importlib.import_module("nidaqmx")
            pytest.skip("nidaqmx is installed -- error-path test doesn't apply")
        except ImportError:
            pass

        result = subprocess.run(
            [sys.executable, str(LIVE_DAQ), "--device", "Dev1"],
            capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "nidaqmx" in result.stderr
        assert "requirements-daq.txt" in result.stderr
