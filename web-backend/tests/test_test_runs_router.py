def test_list_test_runs(client, seeded_db):
    _, summary = seeded_db
    response = client.get("/test-runs", params={"model_id": summary["model_id"]})
    assert response.status_code == 200
    labels = {row["serial_number"] for row in response.json()}
    assert labels == {f"DEMO-{run['label'].upper()}" for run in summary["runs"]}


def test_get_test_run(client, seeded_db):
    _, summary = seeded_db
    test_run_id = summary["runs"][0]["test_run_id"]
    response = client.get(f"/test-runs/{test_run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["test_run"]["test_run_id"] == test_run_id
    assert len(body["dc_records"]) == 1
    assert body["dc_records"][0]["dc_id"] == summary["runs"][0]["dc_id"]


def test_get_test_run_missing_returns_404(client):
    response = client.get("/test-runs/NO-SUCH-RUN")
    assert response.status_code == 404
