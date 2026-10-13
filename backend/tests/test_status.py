def test_status_reports_database_ok(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "JURISCAN-AI"
    assert body["database"] == "ok"


def test_status_schema_shape(client):
    resp = client.get("/api/status")
    body = resp.json()
    assert set(body.keys()) == {"status", "app", "environment", "database", "database_details"}