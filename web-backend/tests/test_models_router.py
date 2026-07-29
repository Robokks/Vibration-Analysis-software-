def test_list_models(client, seeded_db):
    _, summary = seeded_db
    response = client.get("/models")
    assert response.status_code == 200
    ids = [row["model_id"] for row in response.json()]
    assert summary["model_id"] in ids


def test_get_model(client, seeded_db):
    _, summary = seeded_db
    response = client.get(f"/models/{summary['model_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["drive_teeth"]["R"] == 12
    assert body["ratios"]["R"] == 3.753


def test_get_model_missing_returns_404(client):
    response = client.get("/models/NO-SUCH-MODEL")
    assert response.status_code == 404


def test_list_programs(client, seeded_db):
    _, summary = seeded_db
    response = client.get(f"/models/{summary['model_id']}/programs")
    assert response.status_code == 200
    names = [row["program_name"] for row in response.json()]
    assert "REVA" in names


def test_list_parameters(client, seeded_db):
    _, summary = seeded_db
    response = client.get(
        f"/models/{summary['model_id']}/programs/REVA/parameters",
        params={"gear_label": "R", "direction": "RU", "channel_name": "vib_a"},
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == summary["n_table_config_parameter_rows"]
    rms = next(row for row in rows if row["stat_name"] == "RMS Avg")
    assert rms["master"] is not None
    assert rms["limit_low"] is not None
    assert rms["included_in_table_config"] is True
