"""Tests for GET /plc/state -- serves LiveRelay's cache (Phase O Bug 4)."""

from __future__ import annotations


class PlcStateRouterTests:
    def test_default_state_is_idle_and_negative_one(self, client):
        # Before any plc_state event lands on the SUB, the cache holds
        # sensible defaults so the dashboard bridge's heartbeat has
        # something well-formed to serialize.
        r = client.get("/plc/state")
        assert r.status_code == 200
        body = r.json()
        assert body == {
            "nvh_cmd": "IDLE",
            "gear_id": -1,
            "nvh_id": -1,
            "final_log_trigger": False,
        }

    def test_cache_updates_when_relay_sees_plc_state_message(self, client):
        # Drive the cache directly (bypasses the async recv loop -- we
        # don't need a real ZMQ producer for this unit-scope check).
        app_state = client.app.state
        app_state.live_relay._plc_state_cache = {
            "nvh_cmd": "START",
            "gear_id": 2,
            "nvh_id": 1,
            "final_log_trigger": False,
        }
        r = client.get("/plc/state")
        assert r.json()["gear_id"] == 2
        assert r.json()["nvh_id"] == 1
