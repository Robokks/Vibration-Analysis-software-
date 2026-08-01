"""Backend tests for /dashboard/context (Phase K)."""

from __future__ import annotations


class DashboardRouterTests:
    def test_post_creates_context(self, client):
        body = {
            "station_id": "STATION-1", "model_name": "MODEL-A",
            "serial_no": "SN-42", "serial_rpt": "2", "operator_name": "Alex",
        }
        r = client.post("/dashboard/context", json=body)
        assert r.status_code == 200
        assert r.json()["operator_name"] == "Alex"

    def test_get_returns_persisted_row(self, client):
        client.post("/dashboard/context", json={
            "station_id": "S2", "model_name": "MODEL-A",
            "serial_no": "SN-1", "serial_rpt": "1",
        })
        r = client.get("/dashboard/context/S2")
        assert r.status_code == 200
        assert r.json()["station_id"] == "S2"

    def test_get_404_for_unknown_station(self, client):
        r = client.get("/dashboard/context/NEVER-EXISTED")
        assert r.status_code == 404

    def test_post_upserts_existing(self, client):
        client.post("/dashboard/context", json={
            "station_id": "S3", "model_name": "OLD",
            "serial_no": "OLD-SN", "serial_rpt": "1",
        })
        client.post("/dashboard/context", json={
            "station_id": "S3", "model_name": "NEW",
            "serial_no": "NEW-SN", "serial_rpt": "5",
            "operator_name": "Bob",
        })
        r = client.get("/dashboard/context/S3")
        assert r.json()["model_name"] == "NEW"
        assert r.json()["operator_name"] == "Bob"
