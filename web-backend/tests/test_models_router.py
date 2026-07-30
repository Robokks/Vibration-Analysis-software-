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


def _patch_threshold(client, summary, stat_name, threshold_low, threshold_high, **overrides):
    params = {"gear_label": "R", "direction": "RU", "channel_name": "vib_a", **overrides}
    return client.patch(
        f"/models/{summary['model_id']}/programs/REVA/limit-configs/{stat_name}/threshold",
        params=params,
        json={"threshold_low": threshold_low, "threshold_high": threshold_high},
    )


def test_patch_threshold_updates_only_threshold_columns(client, seeded_db):
    _, summary = seeded_db
    # Grab the row's LIMIT band up front so we can assert it's untouched after the PATCH.
    before = client.get(
        f"/models/{summary['model_id']}/programs/REVA/parameters",
        params={"gear_label": "R", "direction": "RU", "channel_name": "vib_a"},
    ).json()
    rms_before = next(r for r in before if r["stat_name"] == "RMS Avg")

    response = _patch_threshold(client, summary, "RMS Avg", 0.05, 0.1)
    assert response.status_code == 200
    body = response.json()
    assert body["stat_name"] == "RMS Avg"
    assert body["threshold_low"] == 0.05
    assert body["threshold_high"] == 0.1
    # LIMIT band, master, and included-in-table-config all stay exactly as before.
    assert body["limit_low"] == rms_before["limit_low"]
    assert body["limit_high"] == rms_before["limit_high"]
    assert body["master"] == rms_before["master"]
    assert body["included_in_table_config"] == rms_before["included_in_table_config"]


def test_patch_threshold_persists_across_a_fresh_get(client, seeded_db):
    _, summary = seeded_db
    _patch_threshold(client, summary, "RMS Avg", 0.07, 0.09)

    refreshed = client.get(
        f"/models/{summary['model_id']}/programs/REVA/parameters",
        params={"gear_label": "R", "direction": "RU", "channel_name": "vib_a"},
    ).json()
    rms = next(r for r in refreshed if r["stat_name"] == "RMS Avg")
    assert rms["threshold_low"] == 0.07
    assert rms["threshold_high"] == 0.09


def test_patch_threshold_unknown_stat_name_returns_404(client, seeded_db):
    _, summary = seeded_db
    response = _patch_threshold(client, summary, "NoSuchParam", 0.0, 0.0)
    assert response.status_code == 404


def test_patch_threshold_unknown_model_returns_404(client, seeded_db):
    response = client.patch(
        "/models/NO-SUCH-MODEL/programs/REVA/limit-configs/RMS%20Avg/threshold",
        params={"gear_label": "R", "direction": "RU"},
        json={"threshold_low": 0.0, "threshold_high": 0.0},
    )
    assert response.status_code == 404


def test_patch_threshold_rejects_missing_body_fields(client, seeded_db):
    _, summary = seeded_db
    response = client.patch(
        f"/models/{summary['model_id']}/programs/REVA/limit-configs/RMS%20Avg/threshold",
        params={"gear_label": "R", "direction": "RU"},
        json={"threshold_low": 0.05},  # missing threshold_high
    )
    assert response.status_code == 422
