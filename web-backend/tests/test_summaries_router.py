"""Backend tests for POST /summaries + GET /summaries (Phase J).

Uses the same seeded_db + client fixtures every other router test uses."""

from __future__ import annotations


class SummariesRouterTests:
    def test_create_summary_returns_row_with_id_and_timestamp(self, client):
        body = {
            "test_run_id": "run-1", "dc_id": "dc-1",
            "model_id": "MODEL-A", "serial_no": "SN-1", "serial_rpt": "1",
            "gear_id": 1, "nvh_id": 0,
            "rms_avg": 0.42, "peak": 1.0, "order_1x_mag": 0.31,
            "stamp": "PASS", "fail_reason_codes": [],
        }
        response = client.post("/summaries", json=body)
        assert response.status_code == 200
        payload = response.json()
        assert payload["summary_id"]
        assert payload["created_at"]
        assert payload["gear_id"] == 1
        assert payload["nvh_id"] == 0
        assert payload["fail_reason_codes"] == []

    def test_list_summaries_returns_created_row(self, client):
        client.post("/summaries", json={
            "test_run_id": "r", "dc_id": "d",
            "model_id": "MODEL-A", "serial_no": "SN-1", "serial_rpt": "1",
            "gear_id": 1, "nvh_id": 3,
        })
        response = client.get("/summaries")
        assert response.status_code == 200
        payloads = response.json()
        assert any(p["nvh_id"] == 3 for p in payloads)

    def test_list_summaries_filters_by_model_id(self, client):
        client.post("/summaries", json={
            "test_run_id": "r1", "dc_id": "d1",
            "model_id": "MODEL-A", "serial_no": "SN-1", "serial_rpt": "1",
            "gear_id": 1, "nvh_id": 0,
        })
        client.post("/summaries", json={
            "test_run_id": "r2", "dc_id": "d2",
            "model_id": "OTHER", "serial_no": "SN-2", "serial_rpt": "1",
            "gear_id": 1, "nvh_id": 0,
        })
        response = client.get("/summaries?model_id=MODEL-A")
        assert response.status_code == 200
        payloads = response.json()
        assert all(p["model_id"] == "MODEL-A" for p in payloads)

    def test_duplicate_post_is_idempotent(self, client):
        # Phase O Bug 9: two identical POSTs (transient network retry
        # scenario) must yield exactly one row + a 200 on the second,
        # not a second row with a fresh uuid.
        body = {
            "test_run_id": "dup-run", "dc_id": "dup-dc",
            "model_id": "MODEL-A", "serial_no": "SN-DUP", "serial_rpt": "1",
            "gear_id": 1, "nvh_id": 0,
            "rms_avg": 0.5,
        }
        first = client.post("/summaries", json=body)
        second = client.post("/summaries", json=body)
        assert first.status_code == 200
        assert second.status_code == 200
        # Same summary_id both times -- the second call returned the
        # existing row rather than minting a new one.
        assert first.json()["summary_id"] == second.json()["summary_id"]

        # List confirms only ONE row for this (test_run_id, dc_id, gear, nvh).
        listed = client.get("/summaries").json()
        matching = [
            r for r in listed
            if r["test_run_id"] == "dup-run" and r["dc_id"] == "dup-dc"
            and r["gear_id"] == 1 and r["nvh_id"] == 0
        ]
        assert len(matching) == 1

    def test_serial_rpt_accepts_non_numeric_string(self, client):
        # Phase O Bug 5: serial_rpt used to be Integer/int, which broke
        # legitimate operator inputs like "R2" from the dashboard side
        # (where IngestContextIn.serial_rpt is str). Now unified as str
        # across both tables + both wire schemas.
        body = {
            "test_run_id": "run-r2", "dc_id": "dc-r2",
            "model_id": "MODEL-A", "serial_no": "SN-99", "serial_rpt": "R2",
            "gear_id": 1, "nvh_id": 0,
        }
        response = client.post("/summaries", json=body)
        assert response.status_code == 200
        assert response.json()["serial_rpt"] == "R2"

        # And the round-trip via GET preserves it verbatim.
        got = client.get("/summaries").json()
        assert any(p["serial_rpt"] == "R2" for p in got)

    def test_create_persists_fail_reason_codes_as_json(self, client):
        body = {
            "test_run_id": "r3", "dc_id": "d3",
            "model_id": "MODEL-A", "serial_no": "SN-3", "serial_rpt": "1",
            "gear_id": 2, "nvh_id": 1,
            "stamp": "FAIL", "fail_reason_codes": ["CRASH_NOISE", "SLIPPAGE"],
        }
        response = client.post("/summaries", json=body)
        assert response.status_code == 200
        payload = response.json()
        assert payload["fail_reason_codes"] == ["CRASH_NOISE", "SLIPPAGE"]
