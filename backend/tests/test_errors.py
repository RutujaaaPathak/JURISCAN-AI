from fastapi import FastAPI

from app.core.exceptions import NotFoundError


def test_app_error_handler_returns_structured_body(client):
    test_app: FastAPI = client.app

    def raises_not_found():
        raise NotFoundError("Widget 42 not found.")

    test_app.add_api_route("/api/_test/not-found", raises_not_found, methods=["GET"])
    resp = client.get("/api/_test/not-found")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Widget 42 not found."


def test_request_validation_returns_422(client):
    from main import app as main_app
    from app.schemas.documents import DocumentCreate

    def create_document(payload: DocumentCreate) -> dict:
        return {"ok": True}

    main_app.add_api_route("/api/_test/documents", create_document, methods=["POST"])
    resp = client.post(
        "/api/_test/documents",
        json={"user_id": "not-an-int", "title": "", "filename": "", "file_type": ""},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert "details" in body["error"]


def test_unhandled_exception_returns_json_500_when_debug_off():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI(debug=False)
    register_exception_handlers(test_app)

    def boom():
        raise RuntimeError("kaboom")

    test_app.add_api_route("/boom", boom, methods=["GET"])
    with TestClient(test_app, raise_server_exceptions=False) as c:
        resp = c.get("/boom")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["code"] == "internal_error"
        assert "unexpected error" in body["error"]["message"]


def test_unhandled_exception_in_debug_mode_returns_500(client):
    from main import app as main_app

    def boom():
        raise RuntimeError("kaboom")

    main_app.add_api_route("/api/_test/boom-debug", boom, methods=["GET"])
    resp = client.get("/api/_test/boom-debug")
    assert resp.status_code == 500


def test_exception_handlers_registered():
    from main import app as main_app

    handlers = main_app.exception_handlers
    assert any("AppError" in str(h) for h in handlers)
    assert any("RequestValidationError" in str(h) for h in handlers)