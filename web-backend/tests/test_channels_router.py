"""Tests for GET /models/{model_id}/channels (Phase L)."""

from __future__ import annotations


class ChannelsRouterTests:
    def test_returns_empty_list_for_seeded_model_without_channel_rows(self, client):
        # The demo seed doesn't populate ChannelRow (that table is
        # written by real acquisition, not by seed_demo_data.py), so
        # the endpoint returns [] for MODEL-A but still 200s.
        response = client.get("/models/MODEL-A/channels")
        assert response.status_code == 200
        assert response.json() == []

    def test_404_for_unknown_model(self, client):
        r = client.get("/models/NEVER-EXISTED/channels")
        assert r.status_code == 404

    def test_returns_configured_channels(self, client, seeded_db):
        from nvh_contract.db import ChannelRow, DcRecordRow, TestRunRow, make_engine, make_session_factory

        db_url, _ = seeded_db
        engine = make_engine(db_url)
        session_factory = make_session_factory(engine)
        with session_factory() as sess:
            # Pick any DC that belongs to MODEL-A.
            dc = (
                sess.query(DcRecordRow)
                .join(TestRunRow, DcRecordRow.test_run_id == TestRunRow.test_run_id)
                .filter(TestRunRow.model_id == "MODEL-A")
                .first()
            )
            assert dc is not None
            sess.add(ChannelRow(
                channel_id="ch-vib", dc_id=dc.dc_id, channel_name="vib_a",
                sensor_type="accel", units="g",
                sensitivity_mv_per_eu=100.0, pregain_db=0.0,
                weighting_filter="linear", is_reference_accel=True,
            ))
            sess.commit()

        payload = client.get("/models/MODEL-A/channels").json()
        assert any(c["channel_name"] == "vib_a" for c in payload)
        row = next(c for c in payload if c["channel_name"] == "vib_a")
        assert set(row.keys()) == {
            "channel_name", "sensor_type", "units",
            "sensitivity_mv_per_eu", "pregain_db", "weighting_filter",
            "is_reference_accel",
        }
        assert row["is_reference_accel"] is True
