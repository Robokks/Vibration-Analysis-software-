"""Smoke checks for dashboard_simulator.py -- the Phase N no-DataSocket
peer of dashboard_bridge.py."""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError


REPO_ROOT = Path(__file__).resolve().parents[2]
DASH_SIM = REPO_ROOT / "web-backend" / "scripts" / "dashboard_simulator.py"


def _load_bridge():
    spec = importlib.util.spec_from_file_location("dashboard_simulator", DASH_SIM)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_simulator"] = module
    spec.loader.exec_module(module)
    return module


class DashboardSimulatorScriptTests:
    def test_help_advertises_expected_flags(self):
        result = subprocess.run(
            [sys.executable, str(DASH_SIM), "--help"],
            capture_output=True, text=True, check=True,
        )
        assert "--backend-url" in result.stdout
        assert "--station-id" in result.stdout
        assert "--interval" in result.stdout
        assert "--once" in result.stdout

    def test_scripted_sequence_has_multiple_entries(self):
        module = _load_bridge()
        seq = module.SCRIPTED_SEQUENCE
        assert len(seq) >= 2
        # Each entry: (model_name, serial_no, serial_rpt, operator_name).
        for entry in seq:
            assert len(entry) == 4
            assert isinstance(entry[0], str)  # model_name

    def test_post_context_sends_expected_body(self, monkeypatch):
        module = _load_bridge()

        captured: dict = {}

        class FakeResp:
            def read(self):
                return b""
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["body"] = json.loads(req.data.decode("utf-8"))
            captured["content_type"] = req.get_header("Content-type")
            return FakeResp()

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
        module._post_context("http://backend:8000", "ST-42",
                             ("MODEL-A", "SN-1", "1", "Alex"))

        assert captured["url"] == "http://backend:8000/dashboard/context"
        assert captured["method"] == "POST"
        assert captured["content_type"] == "application/json"
        assert captured["body"] == {
            "station_id": "ST-42",
            "model_name": "MODEL-A",
            "serial_no": "SN-1",
            "serial_rpt": "1",
            "operator_name": "Alex",
        }

    def test_post_context_swallows_errors(self, monkeypatch):
        """The simulator loop must survive a backend-down window --
        matches the fire-and-forget contract in live_simulator's
        _post_summary. Prints to stderr but doesn't raise."""
        module = _load_bridge()

        def fake_urlopen(req, timeout=None):
            raise URLError("backend down")

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
        # No exception should escape.
        module._post_context("http://backend:8000", "ST", ("M", "S", "1", None))
