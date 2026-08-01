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


# ---- PATCH LIMIT band ---------------------------------------------------


def _patch_limit(client, summary, stat_name, limit_low, limit_high, **overrides):
    params = {"gear_label": "R", "direction": "RU", "channel_name": "vib_a", **overrides}
    return client.patch(
        f"/models/{summary['model_id']}/programs/REVA/limit-configs/{stat_name}/limit",
        params=params,
        json={"limit_low": limit_low, "limit_high": limit_high},
    )


def test_patch_limit_updates_only_limit_columns(client, seeded_db):
    _, summary = seeded_db
    before = client.get(
        f"/models/{summary['model_id']}/programs/REVA/parameters",
        params={"gear_label": "R", "direction": "RU", "channel_name": "vib_a"},
    ).json()
    rms_before = next(r for r in before if r["stat_name"] == "RMS Avg")

    response = _patch_limit(client, summary, "RMS Avg", 0.1, 2.0)
    assert response.status_code == 200
    body = response.json()
    assert body["limit_low"] == 0.1
    assert body["limit_high"] == 2.0
    # THRESHOLD band untouched, master untouched, in-table untouched.
    assert body["threshold_low"] == rms_before["threshold_low"]
    assert body["threshold_high"] == rms_before["threshold_high"]
    assert body["master"] == rms_before["master"]
    assert body["included_in_table_config"] == rms_before["included_in_table_config"]


def test_patch_limit_unknown_stat_name_returns_404(client, seeded_db):
    _, summary = seeded_db
    response = _patch_limit(client, summary, "NoSuchParam", 0.0, 0.0)
    assert response.status_code == 404


def test_patch_limit_rejects_missing_body_fields(client, seeded_db):
    _, summary = seeded_db
    response = client.patch(
        f"/models/{summary['model_id']}/programs/REVA/limit-configs/RMS%20Avg/limit",
        params={"gear_label": "R", "direction": "RU"},
        json={"limit_low": 0.05},  # missing limit_high
    )
    assert response.status_code == 422


# ---- PATCH Table Config parameter inclusion ----------------------------


def _patch_table_config(client, summary, stat_name, included, **overrides):
    params = {"gear_label": "R", "direction": "RU", "channel_name": "vib_a", **overrides}
    return client.patch(
        f"/models/{summary['model_id']}/programs/REVA/table-config/parameters/{stat_name}",
        params=params,
        json={"included": included},
    )


def test_patch_table_config_toggle_removes_then_readds(client, seeded_db):
    _, summary = seeded_db
    # Pick a stat_name that seeded_db definitely put in the table -- RMS Avg
    # is in the default catalog.
    off = _patch_table_config(client, summary, "RMS Avg", False)
    assert off.status_code == 200
    assert off.json()["included_in_table_config"] is False

    on = _patch_table_config(client, summary, "RMS Avg", True)
    assert on.status_code == 200
    assert on.json()["included_in_table_config"] is True


def test_patch_table_config_is_idempotent(client, seeded_db):
    _, summary = seeded_db
    first = _patch_table_config(client, summary, "RMS Avg", True)
    assert first.status_code == 200
    assert first.json()["included_in_table_config"] is True
    # Re-including an already-included row is a no-op, not an error.
    second = _patch_table_config(client, summary, "RMS Avg", True)
    assert second.status_code == 200
    assert second.json()["included_in_table_config"] is True


def test_patch_table_config_unknown_stat_name_returns_404(client, seeded_db):
    _, summary = seeded_db
    response = _patch_table_config(client, summary, "NoSuchParam", True)
    assert response.status_code == 404


def test_patch_table_config_rejects_missing_body_field(client, seeded_db):
    _, summary = seeded_db
    response = client.patch(
        f"/models/{summary['model_id']}/programs/REVA/table-config/parameters/RMS%20Avg",
        params={"gear_label": "R", "direction": "RU"},
        json={},  # missing 'included'
    )
    assert response.status_code == 422


# ---- Calibration --------------------------------------------------------


def test_get_calibration_seeds_defaults_on_first_read(client, seeded_db):
    _, summary = seeded_db
    response = client.get(f"/models/{summary['model_id']}/calibrations/vib_a")
    assert response.status_code == 200
    body = response.json()
    # Defaults straight from the LabVIEW manual.
    assert body["sensor_sensitivity_mv_per_eu"] == 1000.0
    assert body["engineering_units"] == "V"
    assert body["db_reference_eu"] == 1.0
    assert body["weighting_filter"] == "linear"
    assert body["pregain_db"] == 0.0


def test_patch_calibration_persists_across_a_fresh_get(client, seeded_db):
    _, summary = seeded_db
    payload = {
        "sensor_sensitivity_mv_per_eu": 100.0, "engineering_units": "g",
        "db_reference_eu": 1.0, "custom_label": "EU", "weighting_filter": "A",
        "pregain_db": 6.0, "last_calibrated_at": "2026-07-30T00:00:00Z",
        "due_at": "2027-07-30",
    }
    patch = client.patch(f"/models/{summary['model_id']}/calibrations/vib_a", json=payload)
    assert patch.status_code == 200
    assert patch.json()["sensor_sensitivity_mv_per_eu"] == 100.0

    refreshed = client.get(f"/models/{summary['model_id']}/calibrations/vib_a").json()
    assert refreshed["engineering_units"] == "g"
    assert refreshed["weighting_filter"] == "A"
    assert refreshed["due_at"] == "2027-07-30"


def test_get_calibration_unknown_model_returns_404(client):
    response = client.get("/models/NO-SUCH-MODEL/calibrations/vib_a")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /models -- create
# ---------------------------------------------------------------------------

_NEW_MODEL_BODY = {
    "model_id": "TEST-NEW",
    "model_name": "Test New Model",
    "drive_teeth": {"1st": 20, "2nd": 18},
    "idler_teeth_1": {"1st": 30, "2nd": 28},
    "layshaft_teeth": {"1st": 40, "2nd": 38},
    "ratios": {"1st": 2.0, "2nd": 1.8},
}


def test_post_model_creates_and_returns_model(client):
    response = client.post("/models", json=_NEW_MODEL_BODY)
    assert response.status_code == 201
    body = response.json()
    assert body["model_id"] == "TEST-NEW"
    assert body["model_name"] == "Test New Model"
    assert body["drive_teeth"]["1st"] == 20
    assert body["ratios"]["2nd"] == 1.8


def test_post_model_persists_across_get(client):
    client.post("/models", json=_NEW_MODEL_BODY)
    response = client.get("/models/TEST-NEW")
    assert response.status_code == 200
    assert response.json()["model_name"] == "Test New Model"


def test_post_model_duplicate_returns_409(client):
    client.post("/models", json=_NEW_MODEL_BODY)
    response = client.post("/models", json=_NEW_MODEL_BODY)
    assert response.status_code == 409


def test_post_model_appears_in_list(client):
    client.post("/models", json=_NEW_MODEL_BODY)
    ids = [m["model_id"] for m in client.get("/models").json()]
    assert "TEST-NEW" in ids


# ---------------------------------------------------------------------------
# PUT /models/{model_id} -- update
# ---------------------------------------------------------------------------


def test_put_model_updates_fields(client, seeded_db):
    _, summary = seeded_db
    model_id = summary["model_id"]
    original = client.get(f"/models/{model_id}").json()
    update_body = {**original}
    update_body.pop("model_id")
    update_body["model_name"] = "Renamed Model"
    response = client.put(f"/models/{model_id}", json=update_body)
    assert response.status_code == 200
    assert response.json()["model_name"] == "Renamed Model"
    assert response.json()["model_id"] == model_id


def test_put_model_persists_across_get(client, seeded_db):
    _, summary = seeded_db
    model_id = summary["model_id"]
    original = client.get(f"/models/{model_id}").json()
    update_body = {**original}
    update_body.pop("model_id")
    update_body["model_name"] = "Persisted Name"
    client.put(f"/models/{model_id}", json=update_body)
    assert client.get(f"/models/{model_id}").json()["model_name"] == "Persisted Name"


def test_put_model_unknown_returns_404(client):
    response = client.put("/models/NO-SUCH", json={
        "model_name": "X", "drive_teeth": {}, "idler_teeth_1": {},
        "layshaft_teeth": {}, "ratios": {},
    })
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /models/{model_id}
# ---------------------------------------------------------------------------


def test_delete_model_removes_from_list(client):
    client.post("/models", json=_NEW_MODEL_BODY)
    response = client.delete("/models/TEST-NEW")
    assert response.status_code == 204
    ids = [m["model_id"] for m in client.get("/models").json()]
    assert "TEST-NEW" not in ids


def test_delete_model_unknown_returns_404(client):
    response = client.delete("/models/NO-SUCH")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /models/{model_id}/programs -- create program
# ---------------------------------------------------------------------------


def test_post_program_creates_and_returns(client, seeded_db):
    _, summary = seeded_db
    response = client.post(f"/models/{summary['model_id']}/programs", json={"program_name": "REVB"})
    assert response.status_code == 201
    body = response.json()
    assert body["program_name"] == "REVB"
    assert body["model_id"] == summary["model_id"]


def test_post_program_appears_in_list(client, seeded_db):
    _, summary = seeded_db
    client.post(f"/models/{summary['model_id']}/programs", json={"program_name": "REVB"})
    names = [p["program_name"] for p in client.get(f"/models/{summary['model_id']}/programs").json()]
    assert "REVB" in names


def test_post_program_duplicate_returns_409(client, seeded_db):
    _, summary = seeded_db
    response = client.post(f"/models/{summary['model_id']}/programs", json={"program_name": "REVA"})
    assert response.status_code == 409


def test_post_program_unknown_model_returns_404(client):
    response = client.post("/models/NO-SUCH/programs", json={"program_name": "REVA"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /models/{model_id}/programs/{program_name}
# ---------------------------------------------------------------------------


def test_delete_program_removes_from_list(client, seeded_db):
    _, summary = seeded_db
    model_id = summary["model_id"]
    client.post(f"/models/{model_id}/programs", json={"program_name": "REVB"})
    response = client.delete(f"/models/{model_id}/programs/REVB")
    assert response.status_code == 204
    names = [p["program_name"] for p in client.get(f"/models/{model_id}/programs").json()]
    assert "REVB" not in names


def test_delete_program_unknown_returns_404(client, seeded_db):
    _, summary = seeded_db
    response = client.delete(f"/models/{summary['model_id']}/programs/NO-SUCH-PROG")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST .../import-from-master
# ---------------------------------------------------------------------------


def test_import_from_master_seeds_limit_configs(client, seeded_db):
    _, summary = seeded_db
    model_id = summary["model_id"]
    # Create a fresh program with no limit configs.
    client.post(f"/models/{model_id}/programs", json={"program_name": "REVB"})
    response = client.post(
        f"/models/{model_id}/programs/REVB/import-from-master",
        params={"gear_label": "R", "direction": "RU", "channel_name": "vib_a"},
    )
    assert response.status_code == 200
    rows = response.json()
    # Should return at least one row with a non-null limit_low (seeded from master).
    rows_with_limits = [r for r in rows if r["limit_low"] is not None]
    assert len(rows_with_limits) > 0


def test_import_from_master_preserves_existing_thresholds(client, seeded_db):
    _, summary = seeded_db
    model_id = summary["model_id"]
    # Tune REVA's "RMS Avg" threshold, then re-import and check threshold survives.
    _patch_threshold(client, summary, "RMS Avg", 0.07, 0.09)
    client.post(
        f"/models/{model_id}/programs/REVA/import-from-master",
        params={"gear_label": "R", "direction": "RU", "channel_name": "vib_a"},
    )
    refreshed = client.get(
        f"/models/{model_id}/programs/REVA/parameters",
        params={"gear_label": "R", "direction": "RU"},
    ).json()
    rms = next(r for r in refreshed if r["stat_name"] == "RMS Avg")
    assert rms["threshold_low"] == 0.07
    assert rms["threshold_high"] == 0.09


def test_import_from_master_unknown_program_returns_404(client, seeded_db):
    _, summary = seeded_db
    response = client.post(
        f"/models/{summary['model_id']}/programs/NO-SUCH/import-from-master",
        params={"gear_label": "R", "direction": "RU"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST .../limit-configs -- create / upsert individual entry
# ---------------------------------------------------------------------------


def _post_limit_config(client, summary, **overrides):
    payload = {
        "gear_label": "R", "direction": "RU", "channel_name": "vib_a",
        "stat_name": "RMS Avg", "limit_low": 1.0, "limit_high": 5.0,
        **overrides,
    }
    return client.post(
        f"/models/{summary['model_id']}/programs/REVA/limit-configs",
        json=payload,
    )


def test_post_limit_config_creates_entry(client, seeded_db):
    _, summary = seeded_db
    response = _post_limit_config(client, summary, limit_low=0.5, limit_high=3.0)
    assert response.status_code == 201
    body = response.json()
    assert body["stat_name"] == "RMS Avg"
    assert body["limit_low"] == 0.5
    assert body["limit_high"] == 3.0


def test_post_limit_config_upserts_existing(client, seeded_db):
    _, summary = seeded_db
    _post_limit_config(client, summary, limit_low=1.0, limit_high=4.0)
    response = _post_limit_config(client, summary, limit_low=2.0, limit_high=6.0)
    assert response.status_code == 201
    assert response.json()["limit_low"] == 2.0
    assert response.json()["limit_high"] == 6.0


def test_post_limit_config_unknown_model_returns_404(client):
    response = client.post(
        "/models/NO-SUCH/programs/REVA/limit-configs",
        json={"gear_label": "R", "direction": "RU", "stat_name": "RMS Avg",
              "limit_low": 1.0, "limit_high": 5.0},
    )
    assert response.status_code == 404


def test_post_limit_config_unknown_program_returns_404(client, seeded_db):
    _, summary = seeded_db
    response = client.post(
        f"/models/{summary['model_id']}/programs/NO-SUCH/limit-configs",
        json={"gear_label": "R", "direction": "RU", "stat_name": "RMS Avg",
              "limit_low": 1.0, "limit_high": 5.0},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE .../limit-configs/{stat_name}
# ---------------------------------------------------------------------------


def test_delete_limit_config_removes_entry(client, seeded_db):
    _, summary = seeded_db
    model_id = summary["model_id"]
    response = client.delete(
        f"/models/{model_id}/programs/REVA/limit-configs/RMS%20Avg",
        params={"gear_label": "R", "direction": "RU", "channel_name": "vib_a"},
    )
    assert response.status_code == 204
    refreshed = client.get(
        f"/models/{model_id}/programs/REVA/parameters",
        params={"gear_label": "R", "direction": "RU"},
    ).json()
    rms = next((r for r in refreshed if r["stat_name"] == "RMS Avg"), None)
    # Row may still appear if a master signature exists, but limit_low is now None.
    if rms is not None:
        assert rms["limit_low"] is None


def test_delete_limit_config_unknown_returns_404(client, seeded_db):
    _, summary = seeded_db
    response = client.delete(
        f"/models/{summary['model_id']}/programs/REVA/limit-configs/NoSuchStat",
        params={"gear_label": "R", "direction": "RU"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Table config steps: GET / PUT / DELETE
# ---------------------------------------------------------------------------


def test_list_table_config_steps_empty_for_new_program(client, seeded_db):
    _, summary = seeded_db
    model_id = summary["model_id"]
    client.post(f"/models/{model_id}/programs", json={"program_name": "REVB"})
    response = client.get(f"/models/{model_id}/programs/REVB/table-config/steps")
    assert response.status_code == 200
    assert response.json() == []


def test_put_table_config_step_creates_entry(client, seeded_db):
    _, summary = seeded_db
    model_id = summary["model_id"]
    client.post(f"/models/{model_id}/programs", json={"program_name": "REVB"})
    response = client.put(
        f"/models/{model_id}/programs/REVB/table-config/steps",
        json={"gear_label": "R", "direction": "RU", "channel_name": "vib_a", "step_order": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["gear_label"] == "R"
    assert body["direction"] == "RU"
    assert body["step_order"] == 1


def test_put_table_config_step_updates_order(client, seeded_db):
    _, summary = seeded_db
    model_id = summary["model_id"]
    client.post(f"/models/{model_id}/programs", json={"program_name": "REVB"})
    client.put(
        f"/models/{model_id}/programs/REVB/table-config/steps",
        json={"gear_label": "R", "direction": "RU", "step_order": 1},
    )
    response = client.put(
        f"/models/{model_id}/programs/REVB/table-config/steps",
        json={"gear_label": "R", "direction": "RU", "step_order": 3},
    )
    assert response.status_code == 200
    assert response.json()["step_order"] == 3


def test_put_table_config_step_appears_in_list(client, seeded_db):
    _, summary = seeded_db
    model_id = summary["model_id"]
    client.post(f"/models/{model_id}/programs", json={"program_name": "REVB"})
    client.put(
        f"/models/{model_id}/programs/REVB/table-config/steps",
        json={"gear_label": "R", "direction": "RU", "step_order": 1},
    )
    client.put(
        f"/models/{model_id}/programs/REVB/table-config/steps",
        json={"gear_label": "R", "direction": "STYD", "step_order": 2},
    )
    steps = client.get(f"/models/{model_id}/programs/REVB/table-config/steps").json()
    assert len(steps) == 2
    assert steps[0]["step_order"] == 1  # sorted by step_order


def test_delete_table_config_step_removes_entry(client, seeded_db):
    _, summary = seeded_db
    model_id = summary["model_id"]
    client.post(f"/models/{model_id}/programs", json={"program_name": "REVB"})
    client.put(
        f"/models/{model_id}/programs/REVB/table-config/steps",
        json={"gear_label": "R", "direction": "RU", "step_order": 1},
    )
    response = client.delete(
        f"/models/{model_id}/programs/REVB/table-config/steps",
        params={"gear_label": "R", "direction": "RU"},
    )
    assert response.status_code == 204
    assert client.get(f"/models/{model_id}/programs/REVB/table-config/steps").json() == []


def test_delete_table_config_step_unknown_returns_404(client, seeded_db):
    _, summary = seeded_db
    response = client.delete(
        f"/models/{summary['model_id']}/programs/REVA/table-config/steps",
        params={"gear_label": "NO-GEAR", "direction": "RU"},
    )
    assert response.status_code == 404
