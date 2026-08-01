def test_summary_report_aggregates_all_dc_records_for_the_gear_direction(client, seeded_db):
    _, summary = seeded_db
    response = client.get(
        f"/models/{summary['model_id']}/summary",
        params={"gear_label": "R", "direction": "RU", "stat_name": "RMS Avg"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stat_name"] == "RMS Avg"
    assert len(body["rows"]) == len(summary["runs"])
    assert "center_line" in body["xchart"]
    assert "bin_edges" in body["histogram"]


def test_summary_report_missing_model_returns_404(client):
    response = client.get(
        "/models/NO-SUCH-MODEL/summary",
        params={"gear_label": "R", "direction": "RU", "stat_name": "RMS Avg"},
    )
    assert response.status_code == 404


def test_summary_report_no_matching_dc_records_returns_404(client, seeded_db):
    _, summary = seeded_db
    response = client.get(
        f"/models/{summary['model_id']}/summary",
        params={"gear_label": "R", "direction": "STYC", "stat_name": "RMS Avg"},
    )
    assert response.status_code == 404
