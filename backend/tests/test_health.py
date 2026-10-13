def test_health_returns_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "JURISCAN-AI"
    assert body["environment"] in {"development", "test", "production", "staging"}


def test_cors_preflight_allowed(client):
    resp = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code in {200, 405}
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_unknown_route_returns_structured_404(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "http_error"
    assert "message" in body["error"]