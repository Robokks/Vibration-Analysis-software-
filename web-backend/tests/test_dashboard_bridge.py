"""Tests for the dashboard bridge loop -- exercised with an in-memory
fake DataSocket client so the real COM binding never runs.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BRIDGE = REPO_ROOT / "web-backend" / "scripts" / "dashboard_bridge.py"


def _load_bridge():
    spec = importlib.util.spec_from_file_location("dashboard_bridge", BRIDGE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_bridge"] = module
    spec.loader.exec_module(module)
    return module


class FakeClient:
    def __init__(self, context_sequence):
        self._context_sequence = list(context_sequence)
        self._i = 0
        self.heartbeats: list[dict] = []

    def read_context(self):
        if self._i < len(self._context_sequence):
            value = self._context_sequence[self._i]
            self._i += 1
            return value
        return self._context_sequence[-1] if self._context_sequence else None

    def write_heartbeat(self, blob):
        self.heartbeats.append(blob)


class DashboardBridgeTests:
    def test_context_change_posts_to_backend(self, monkeypatch):
        bridge = _load_bridge()
        posts: list[dict] = []

        def _fake_post(backend_url: str, body: dict):
            posts.append(body)

        monkeypatch.setattr(bridge, "_post_context", _fake_post)

        client = FakeClient([
            {"model_name": "MODEL-A", "serial_no": "SN-1", "serial_rpt": "1"},
            {"model_name": "MODEL-A", "serial_no": "SN-1", "serial_rpt": "1"},  # unchanged
            {"model_name": "MODEL-B", "serial_no": "SN-2", "serial_rpt": "3"},
        ])

        bridge.run_bridge(
            backend_url="http://ignored", station_id="ST-1",
            poll_hz=100.0, heartbeat_hz=100.0,
            client_factory=lambda: client, max_iterations=3,
        )

        assert len(posts) == 2  # unchanged tick shouldn't re-POST
        assert posts[0]["serial_no"] == "SN-1"
        assert posts[1]["serial_no"] == "SN-2"
        assert posts[1]["station_id"] == "ST-1"

    def test_heartbeat_writes_each_period(self, monkeypatch):
        bridge = _load_bridge()
        monkeypatch.setattr(bridge, "_post_context", lambda *a, **k: None)
        # Phase O Bug 4: heartbeat fetches PLC state from the backend.
        # Stub the fetch out so this test doesn't need a live backend.
        monkeypatch.setattr(bridge, "_fetch_plc_state",
                            lambda *_a, **_k: {"gear_id": -1, "nvh_id": -1})

        client = FakeClient([{"model_name": "M", "serial_no": "S", "serial_rpt": "1"}])
        bridge.run_bridge(
            backend_url="http://ignored", station_id="ST",
            poll_hz=100.0, heartbeat_hz=1000.0,
            client_factory=lambda: client, max_iterations=3,
        )
        assert len(client.heartbeats) >= 1
        blob = client.heartbeats[-1]
        assert blob["status"] == "OK"
        assert "timestamp" in blob
        assert "current_gear_id" in blob

    def test_heartbeat_uses_current_plc_state_from_backend(self, monkeypatch):
        # Phase O Bug 4: previously the heartbeat pulled gear/nvh from
        # `last_context` (the dashboard-IN payload), which never contains
        # those keys. Fix: fetch them from the backend's PLC-state cache.
        bridge = _load_bridge()
        monkeypatch.setattr(bridge, "_post_context", lambda *a, **k: None)
        monkeypatch.setattr(bridge, "_fetch_plc_state",
                            lambda *_a, **_k: {"gear_id": 3, "nvh_id": 1})

        client = FakeClient([{"model_name": "M", "serial_no": "S", "serial_rpt": "1"}])
        bridge.run_bridge(
            backend_url="http://ignored", station_id="ST",
            poll_hz=100.0, heartbeat_hz=1000.0,
            client_factory=lambda: client, max_iterations=3,
        )
        assert client.heartbeats
        assert client.heartbeats[-1]["current_gear_id"] == 3
        assert client.heartbeats[-1]["current_nvh_id"] == 1

    def test_context_change_with_comma_in_operator_name_still_posts(self, monkeypatch):
        # Phase O Bug 6 (dashboard side): the FakeClient here mirrors the
        # bridge's real DataSocket JSON contract. A payload with a comma
        # in a value used to break the old k=v parser and silently drop
        # the update -- with JSON on the wire it round-trips intact.
        bridge = _load_bridge()
        posts: list[dict] = []
        monkeypatch.setattr(bridge, "_post_context", lambda url, body: posts.append(body))

        client = FakeClient([{
            "model_name": "MODEL-A",
            "serial_no": "SN-1",
            "serial_rpt": "R2",
            "operator_name": "Doe, Jane",  # comma in operator name
        }])
        bridge.run_bridge(
            backend_url="http://ignored", station_id="ST-1",
            poll_hz=100.0, heartbeat_hz=100.0,
            client_factory=lambda: client, max_iterations=2,
        )
        assert posts
        assert posts[0]["operator_name"] == "Doe, Jane"
        assert posts[0]["serial_rpt"] == "R2"
