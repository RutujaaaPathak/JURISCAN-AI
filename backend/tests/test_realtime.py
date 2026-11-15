"""Tests for real-time private workspace messaging over WebSockets.

These exercise the real token-authenticated socket flow (not the HTTP
dependency override, which does not apply to WebSocket connections) and assert
that authorization is enforced per connection and per message event, that
messages are persisted before being broadcast, and that both parties receive
updates without a page reload.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.deps import get_current_user
from app.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models import LawyerProfile, User

CASE_PAYLOAD = {
    "title": "Boundary dispute with neighbour",
    "category": "property",
    "summary": "A fence was built across the shared driveway boundary.",
    "urgency": "MEDIUM",
}


def _make_user(
    role: str, name: str, verification_status: str | None = "VERIFIED"
) -> User:
    db = SessionLocal()
    try:
        user = User(
            email=f"{name}@example.com",
            username=name,
            full_name=name.replace("-", " ").title(),
            role=role,
        )
        db.add(user)
        db.flush()
        if role == "lawyer" and verification_status is not None:
            db.add(
                LawyerProfile(
                    user_id=user.id, verification_status=verification_status
                )
            )
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def _token(user: User, ttl_seconds: int = 3600) -> str:
    return create_access_token(
        user.id, secret=settings.secret_key, ttl_seconds=ttl_seconds
    )


@pytest.fixture
def login(client: TestClient):
    def _login(user: User) -> User:
        client.app.dependency_overrides[get_current_user] = lambda: user
        return user

    yield _login
    client.app.dependency_overrides.clear()


def _assigned_case(client: TestClient, login) -> tuple[User, User, int]:
    client_user = _make_user("individual", "rt-client")
    login(client_user)
    created = client.post("/api/cases", json=CASE_PAYLOAD)
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]

    lawyer = _make_user("lawyer", "rt-lawyer")
    login(lawyer)
    accepted = client.post(f"/api/cases/{case_id}/accept")
    assert accepted.status_code == 200, accepted.text
    return client_user, lawyer, case_id


def _open(
    client: TestClient, case_id: int, user: User, ttl_seconds: int = 3600
):
    websocket = client.websocket_connect(f"/api/cases/{case_id}/ws")
    websocket.__enter__()
    websocket.send_json({"type": "auth", "token": _token(user, ttl_seconds)})
    ready = websocket.receive_json()
    assert ready["type"] == "ready"
    assert ready["user_id"] == user.id
    return websocket


def _close(websocket) -> None:
    websocket.__exit__(None, None, None)


def test_client_message_reaches_lawyer_without_reload(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    websocket = _open(client, case_id, lawyer)
    try:
        login(client_user)
        sent = client.post(f"/api/cases/{case_id}/messages", json={"body": "Hello counsel"})
        assert sent.status_code == 201, sent.text

        event = websocket.receive_json()
        assert event["type"] == "message"
        assert event["message"]["body"] == "Hello counsel"
        assert event["message"]["sender_user_id"] == client_user.id
        # ISO-8601 string, not a raw datetime (frames must be JSON-safe).
        assert isinstance(event["message"]["created_at"], str)
    finally:
        _close(websocket)


def test_lawyer_message_reaches_client_without_reload(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    websocket = _open(client, case_id, client_user)
    try:
        login(lawyer)
        sent = client.post(
            f"/api/cases/{case_id}/messages", json={"body": "Your hearing is next week."}
        )
        assert sent.status_code == 201, sent.text

        event = websocket.receive_json()
        assert event["type"] == "message"
        assert event["message"]["body"] == "Your hearing is next week."
        assert event["message"]["sender_user_id"] == lawyer.id
    finally:
        _close(websocket)


def test_websocket_send_persists_and_broadcasts(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    client_ws = _open(client, case_id, client_user)
    lawyer_ws = _open(client, case_id, lawyer)
    try:
        lawyer_ws.send_json({"type": "message", "body": "Sent over the socket"})
        event = client_ws.receive_json()
        assert event["type"] == "message"
        assert event["message"]["body"] == "Sent over the socket"
        assert event["message"]["sender_user_id"] == lawyer.id
    finally:
        _close(client_ws)
        _close(lawyer_ws)

    login(client_user)
    history = client.get(f"/api/cases/{case_id}/messages")
    assert history.status_code == 200
    bodies = [item["body"] for item in history.json()["items"]]
    assert "Sent over the socket" in bodies


def test_messages_persist_across_reconnect(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    # Delivered live on the first connection...
    first = _open(client, case_id, lawyer)
    try:
        login(client_user)
        assert client.post(
            f"/api/cases/{case_id}/messages", json={"body": "Before disconnect"}
        ).status_code == 201
        assert first.receive_json()["type"] == "message"
    finally:
        _close(first)

    # ...and still present after the socket drops and a new one connects.
    second = _open(client, case_id, lawyer)
    try:
        login(lawyer)
        history = client.get(f"/api/cases/{case_id}/messages")
        bodies = [item["body"] for item in history.json()["items"]]
        assert bodies == ["Before disconnect"]
    finally:
        _close(second)


def test_broadcast_reaches_every_open_tab(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    tab_one = _open(client, case_id, client_user)
    tab_two = _open(client, case_id, client_user)
    try:
        login(lawyer)
        client.post(f"/api/cases/{case_id}/messages", json={"body": "Two tabs"})
        assert tab_one.receive_json()["message"]["body"] == "Two tabs"
        assert tab_two.receive_json()["message"]["body"] == "Two tabs"
    finally:
        _close(tab_one)
        _close(tab_two)


def test_unrelated_user_cannot_subscribe(client: TestClient, login):
    _client_user, _lawyer, case_id = _assigned_case(client, login)
    stranger = _make_user("lawyer", "rt-stranger")

    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/api/cases/{case_id}/ws") as websocket:
            websocket.send_json({"type": "auth", "token": _token(stranger)})
            websocket.receive_json()
    assert excinfo.value.code == 4403


def test_invalid_token_is_rejected(client: TestClient, login):
    _client_user, _lawyer, case_id = _assigned_case(client, login)

    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/api/cases/{case_id}/ws") as websocket:
            websocket.send_json({"type": "auth", "token": "not-a-real-token"})
            websocket.receive_json()
    assert excinfo.value.code == 4401


def test_missing_auth_frame_is_rejected(client: TestClient, login):
    _client_user, _lawyer, case_id = _assigned_case(client, login)

    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/api/cases/{case_id}/ws") as websocket:
            websocket.send_json({"type": "ping"})
            websocket.receive_json()
    assert excinfo.value.code == 4400


def test_ping_is_answered(client: TestClient, login):
    client_user, _lawyer, case_id = _assigned_case(client, login)

    websocket = _open(client, case_id, client_user)
    try:
        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}
    finally:
        _close(websocket)


def test_websocket_send_requires_party_after_assignment_removed(client: TestClient, login):
    """A socket that was valid at connect time must not keep publishing once the
    user is no longer part of the case (authorization is re-checked per event)."""

    client_user, lawyer, case_id = _assigned_case(client, login)

    websocket = _open(client, case_id, client_user)
    try:
        # Simulate the case being reassigned / unassigned out from under the client.
        db = SessionLocal()
        try:
            from app.models import Case

            case = db.get(Case, case_id)
            case.assigned_lawyer_id = None
            db.commit()
        finally:
            db.close()

        websocket.send_json({"type": "message", "body": "still here?"})
        error = websocket.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "not_authorized"
    finally:
        _close(websocket)


def test_empty_websocket_message_is_rejected(client: TestClient, login):
    client_user, _lawyer, case_id = _assigned_case(client, login)

    websocket = _open(client, case_id, client_user)
    try:
        websocket.send_json({"type": "message", "body": "   "})
        error = websocket.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "empty_message"
    finally:
        _close(websocket)


def test_suspended_account_is_disconnected_on_next_event(
    client: TestClient, login
):
    _client_user, lawyer, case_id = _assigned_case(client, login)
    websocket = _open(client, case_id, lawyer)
    try:
        db = SessionLocal()
        try:
            user = db.get(User, lawyer.id)
            user.is_active = False
            db.commit()
        finally:
            db.close()

        websocket.send_json({"type": "message", "body": "still here?"})
        error = websocket.receive_json()
        assert error == {"type": "error", "code": "session_invalid"}

        with pytest.raises(WebSocketDisconnect) as excinfo:
            websocket.receive_json()
        assert excinfo.value.code == 4401
    finally:
        _close(websocket)


def test_expired_token_is_disconnected_on_next_event(
    client: TestClient, login
):
    _client_user, lawyer, case_id = _assigned_case(client, login)
    websocket = _open(client, case_id, lawyer, ttl_seconds=1)
    try:
        time.sleep(2.1)
        websocket.send_json({"type": "ping"})
        error = websocket.receive_json()
        assert error == {"type": "error", "code": "session_invalid"}

        with pytest.raises(WebSocketDisconnect) as excinfo:
            websocket.receive_json()
        assert excinfo.value.code == 4401
    finally:
        _close(websocket)


def test_revoked_token_disconnects_existing_websocket(
    client: TestClient, login
):
    _client_user, lawyer, case_id = _assigned_case(client, login)
    websocket = _open(client, case_id, lawyer)
    try:
        db = SessionLocal()
        try:
            user = db.get(User, lawyer.id)
            user.token_version += 1
            db.commit()
        finally:
            db.close()

        websocket.send_json({"type": "ping"})
        error = websocket.receive_json()
        assert error == {"type": "error", "code": "session_invalid"}

        with pytest.raises(WebSocketDisconnect) as excinfo:
            websocket.receive_json()
        assert excinfo.value.code == 4401
    finally:
        _close(websocket)


def test_revoked_verification_blocks_realtime_messages(
    client: TestClient, login
):
    _client_user, lawyer, case_id = _assigned_case(client, login)
    websocket = _open(client, case_id, lawyer)
    try:
        db = SessionLocal()
        try:
            profile = db.query(LawyerProfile).filter_by(user_id=lawyer.id).one()
            profile.verification_status = "PENDING"
            db.commit()
        finally:
            db.close()

        websocket.send_json({"type": "message", "body": "still allowed?"})
        error = websocket.receive_json()
        assert error == {"type": "error", "code": "not_authorized"}

        with pytest.raises(WebSocketDisconnect) as excinfo:
            websocket.receive_json()
        assert excinfo.value.code == 4403
    finally:
        _close(websocket)
