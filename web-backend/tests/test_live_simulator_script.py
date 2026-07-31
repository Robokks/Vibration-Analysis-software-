"""Smoke checks for `live_simulator.py`'s new TDMS logging flag."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_SIM = REPO_ROOT / "web-backend" / "scripts" / "live_simulator.py"


class LiveSimulatorScriptTests:
    def test_help_advertises_tdms_flag(self):
        result = subprocess.run(
            [sys.executable, str(LIVE_SIM), "--help"],
            capture_output=True, text=True, check=True,
        )
        assert "--tdms-path" in result.stdout
        assert "--pub-url" in result.stdout
