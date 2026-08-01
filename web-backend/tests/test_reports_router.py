import pytest


def _dc_id(summary, label):
    return next(run["dc_id"] for run in summary["runs"] if run["label"] == label)


def test_consolidated_report_healthy_unit_passes(client, seeded_db):
    _, summary = seeded_db
    dc_id = _dc_id(summary, "healthy-unit")
    response = client.get(f"/dc-records/{dc_id}/reports/consolidated")
    assert response.status_code == 200
    body = response.json()
    assert body["stamp"] == "PASS"
    assert body["result"]["passed"] is True


def test_consolidated_report_crash_noise_unit_fails(client, seeded_db):
    _, summary = seeded_db
    dc_id = _dc_id(summary, "crash-noise-unit")
    response = client.get(f"/dc-records/{dc_id}/reports/consolidated")
    assert response.status_code == 200
    body = response.json()
    assert body["stamp"] == "FAIL"
    assert "CRASH_NOISE" in body["result"]["fail_reason_codes"]


def test_consolidated_report_missing_dc_returns_404(client):
    response = client.get("/dc-records/NO-SUCH-DC/reports/consolidated")
    assert response.status_code == 404


def test_detailed_report_has_a_row_per_master_parameter(client, seeded_db):
    _, summary = seeded_db
    dc_id = _dc_id(summary, "healthy-unit")
    response = client.get(f"/dc-records/{dc_id}/reports/detailed")
    assert response.status_code == 200
    body = response.json()
    assert len(body["numeric_table"]) == summary["n_master_params"]
    assert all(row["master"] is not None for row in body["numeric_table"])


def test_code_result_report_without_program_name_is_unfiltered(client, seeded_db):
    _, summary = seeded_db
    dc_id = _dc_id(summary, "healthy-unit")
    response = client.get(f"/dc-records/{dc_id}/reports/code-result")
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == summary["n_master_params"]
    assert all(row["step"] == 1 for row in rows)


def test_code_result_report_with_program_name_is_filtered_and_ordered(client, seeded_db):
    _, summary = seeded_db
    dc_id = _dc_id(summary, "healthy-unit")
    response = client.get(f"/dc-records/{dc_id}/reports/code-result", params={"program_name": "REVA"})
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == summary["n_table_config_parameter_rows"]
    assert all(row["step"] == 1 for row in rows)
    assert all(row["gear_direction"] == "R_RU" for row in rows)


@pytest.mark.parametrize("report_type", ["consolidated", "detailed", "code-result"])
def test_reports_accept_program_name(client, seeded_db, report_type):
    # grading via the LIMIT/THRESHOLD path (program_name given) shouldn't
    # error even though the demo's 3 scenarios were built against masters.
    _, summary = seeded_db
    dc_id = _dc_id(summary, "healthy-unit")
    response = client.get(f"/dc-records/{dc_id}/reports/{report_type}", params={"program_name": "REVA"})
    assert response.status_code == 200
