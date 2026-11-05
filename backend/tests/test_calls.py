"""Tests for real-time voice calling backend foundation.

Covers:
- Authorization: case owner and assigned lawyer only; verification on every API and WebSocket event
- Call lifecycle: ringing, accepted, rejected, missed, ended states and duration calculation
- Invalid transitions: attempting to accept/reject/end terminal or invalid state calls
- Concurrent calls: preventing multiple active calls per case via transactions and unique constraint
- WebSocket WebRTC signaling: auth handshake, offer, answer, ICE candidates, and disconnect handling
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.deps import get_current_user
from app.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models import Call, Case, User

CASE_PAYLOAD = {
    "title": "Property title dispute",
    "category": "property",
    "summary": "Urgent boundary dispute requiring consultation.",
    "urgency": "HIGH",
}


def _make_user(role: str, name: str) -> User:
    db = SessionLocal()
    try:
        user = User(
            email=f"{name}@example.com",
            username=name,
            full_name=name.replace("-", " ").title(),
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def _token(user: User) -> str:
    return create_access_token(user.id, secret=settings.secret_key, ttl_seconds=3600)


@pytest.fixture
def login(client: TestClient):
    def _login(user: User) -> User:
        client.app.dependency_overrides[get_current_user] = lambda: user
        return user

    yield _login
    client.app.dependency_overrides.clear()


def _assigned_case(client: TestClient, login) -> tuple[User, User, int]:
    client_user = _make_user("individual", "call-client")
    login(client_user)
    created = client.post("/api/cases", json=CASE_PAYLOAD)
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]

    lawyer = _make_user("lawyer", "call-lawyer")
    login(lawyer)
    accepted = client.post(f"/api/cases/{case_id}/accept")
    assert accepted.status_code == 200, accepted.text
    return client_user, lawyer, case_id


def _open_call_ws(client: TestClient, case_id: int, user: User):
    websocket = client.websocket_connect(f"/api/cases/{case_id}/calls/ws")
    websocket.__enter__()
    websocket.send_json({"type": "auth", "token": _token(user)})
    ready = websocket.receive_json()
    assert ready["type"] == "ready"
    assert ready["user_id"] == user.id
    return websocket


def _close_ws(websocket) -> None:
    websocket.__exit__(None, None, None)


# -----------------------------------------------------------------------------
# Authorization Tests
# -----------------------------------------------------------------------------


def test_unassigned_case_cannot_initiate_call(client: TestClient, login):
    client_user = _make_user("individual", "call-client-unassigned")
    login(client_user)
    created = client.post("/api/cases", json=CASE_PAYLOAD)
    case_id = created.json()["id"]

    # No lawyer assigned yet
    resp = client.post(f"/api/cases/{case_id}/calls")
    assert resp.status_code in (400, 409), resp.text


def test_stranger_cannot_initiate_call(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)
    stranger = _make_user("individual", "call-stranger")

    login(stranger)
    resp = client.post(f"/api/cases/{case_id}/calls")
    assert resp.status_code == 403


def test_caller_cannot_accept_own_call(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    login(client_user)
    call_resp = client.post(f"/api/cases/{case_id}/calls")
    assert call_resp.status_code == 201
    call_id = call_resp.json()["id"]

    # Caller attempts to accept
    accept_resp = client.post(f"/api/cases/{case_id}/calls/{call_id}/accept")
    assert accept_resp.status_code == 403


def test_stranger_cannot_accept_or_reject_call(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)
    stranger = _make_user("lawyer", "call-lawyer-stranger")

    login(client_user)
    call_resp = client.post(f"/api/cases/{case_id}/calls")
    call_id = call_resp.json()["id"]

    login(stranger)
    assert client.post(f"/api/cases/{case_id}/calls/{call_id}/accept").status_code == 403
    assert client.post(f"/api/cases/{case_id}/calls/{call_id}/reject").status_code == 403
    assert client.post(f"/api/cases/{case_id}/calls/{call_id}/end").status_code == 403


# -----------------------------------------------------------------------------
# Call Lifecycle Tests
# -----------------------------------------------------------------------------


def test_call_lifecycle_ringing_to_accepted_to_ended(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    # 1. Client initiates call
    login(client_user)
    initiated = client.post(f"/api/cases/{case_id}/calls")
    assert initiated.status_code == 201
    data = initiated.json()
    call_id = data["id"]
    assert data["status"] == "RINGING"
    assert data["caller_id"] == client_user.id
    assert data["receiver_id"] == lawyer.id
    assert data["answered_at"] is None
    assert data["ended_at"] is None

    # Verify active call query returns it
    active = client.get(f"/api/cases/{case_id}/calls/active")
    assert active.status_code == 200
    assert active.json()["active_call"]["id"] == call_id

    # 2. Lawyer accepts call
    login(lawyer)
    accepted = client.post(f"/api/cases/{case_id}/calls/{call_id}/accept")
    assert accepted.status_code == 200
    acc_data = accepted.json()
    assert acc_data["status"] == "ACCEPTED"
    assert acc_data["answered_at"] is not None

    # 3. Client ends the call
    login(client_user)
    ended = client.post(f"/api/cases/{case_id}/calls/{call_id}/end")
    assert ended.status_code == 200
    end_data = ended.json()
    assert end_data["status"] == "ENDED"
    assert end_data["ended_at"] is not None
    assert end_data["duration"] is not None
    assert end_data["duration"] >= 0

    # Verify no active call remains
    active = client.get(f"/api/cases/{case_id}/calls/active")
    assert active.status_code == 200
    assert active.json()["active_call"] is None


def test_call_lifecycle_receiver_rejects(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    login(client_user)
    initiated = client.post(f"/api/cases/{case_id}/calls")
    call_id = initiated.json()["id"]

    login(lawyer)
    rejected = client.post(f"/api/cases/{case_id}/calls/{call_id}/reject?reason=busy")
    assert rejected.status_code == 200
    data = rejected.json()
    assert data["status"] == "REJECTED"
    assert data["ended_at"] is not None
    assert data["duration"] == 0


def test_call_lifecycle_caller_cancels_before_answer_is_missed(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    login(client_user)
    initiated = client.post(f"/api/cases/{case_id}/calls")
    call_id = initiated.json()["id"]

    # Caller hangs up before lawyer answers
    ended = client.post(f"/api/cases/{case_id}/calls/{call_id}/end")
    assert ended.status_code == 200
    data = ended.json()
    assert data["status"] == "MISSED"
    assert data["ended_at"] is not None
    assert data["duration"] == 0


def test_call_history_listing_and_pagination(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    login(client_user)
    call1 = client.post(f"/api/cases/{case_id}/calls").json()["id"]
    client.post(f"/api/cases/{case_id}/calls/{call1}/end")

    call2 = client.post(f"/api/cases/{case_id}/calls").json()["id"]
    client.post(f"/api/cases/{case_id}/calls/{call2}/end")

    history = client.get(f"/api/cases/{case_id}/calls?limit=10")
    assert history.status_code == 200
    body = history.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    # Verify descending ordering
    assert body["items"][0]["id"] == call2
    assert body["items"][1]["id"] == call1


# -----------------------------------------------------------------------------
# Invalid Transition Tests
# -----------------------------------------------------------------------------


def test_cannot_accept_already_accepted_or_ended_call(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    login(client_user)
    call_id = client.post(f"/api/cases/{case_id}/calls").json()["id"]

    login(lawyer)
    assert client.post(f"/api/cases/{case_id}/calls/{call_id}/accept").status_code == 200

    # Attempt to accept again
    re_accept = client.post(f"/api/cases/{case_id}/calls/{call_id}/accept")
    assert re_accept.status_code == 409

    # End the call
    client.post(f"/api/cases/{case_id}/calls/{call_id}/end")

    # Attempt to accept after ended
    after_end = client.post(f"/api/cases/{case_id}/calls/{call_id}/accept")
    assert after_end.status_code == 409


def test_cannot_end_terminal_call(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    login(client_user)
    call_id = client.post(f"/api/cases/{case_id}/calls").json()["id"]
    client.post(f"/api/cases/{case_id}/calls/{call_id}/end")

    # Try ending again
    re_end = client.post(f"/api/cases/{case_id}/calls/{call_id}/end")
    assert re_end.status_code == 409


# -----------------------------------------------------------------------------
# Concurrent Call Prevention & Constraints
# -----------------------------------------------------------------------------


def test_prevent_multiple_simultaneous_active_calls(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    # 1. Client initiates call (ringing)
    login(client_user)
    first = client.post(f"/api/cases/{case_id}/calls")
    assert first.status_code == 201

    # 2. Lawyer concurrently attempts to initiate a call for the same case
    login(lawyer)
    second = client.post(f"/api/cases/{case_id}/calls")
    assert second.status_code == 409

    # 3. Client also cannot initiate another while first is active
    login(client_user)
    third = client.post(f"/api/cases/{case_id}/calls")
    assert third.status_code == 409

    # 4. Once first call ends, a new call can be initiated
    first_id = first.json()["id"]
    client.post(f"/api/cases/{case_id}/calls/{first_id}/end")

    fourth = client.post(f"/api/cases/{case_id}/calls")
    assert fourth.status_code == 201


# -----------------------------------------------------------------------------
# WebSocket WebRTC Signaling Tests
# -----------------------------------------------------------------------------


def test_websocket_requires_first_frame_auth(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/api/cases/{case_id}/calls/ws") as ws:
            ws.send_json({"type": "ping"})
            ws.receive_json()
    assert excinfo.value.code == 4400


def test_websocket_unauthorized_token_rejected(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/api/cases/{case_id}/calls/ws") as ws:
            ws.send_json({"type": "auth", "token": "invalid-token"})
            ws.receive_json()
    assert excinfo.value.code == 4401


def test_websocket_stranger_cannot_connect(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)
    stranger = _make_user("lawyer", "call-ws-stranger")

    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/api/cases/{case_id}/calls/ws") as ws:
            ws.send_json({"type": "auth", "token": _token(stranger)})
            ws.receive_json()
    assert excinfo.value.code == 4403


def test_websocket_signaling_exchange_offer_answer_and_ice(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    # Both parties connect to signaling WebSocket
    client_ws = _open_call_ws(client, case_id, client_user)
    lawyer_ws = _open_call_ws(client, case_id, lawyer)

    try:
        # Ping check
        client_ws.send_json({"type": "ping"})
        assert client_ws.receive_json() == {"type": "pong"}

        # Client initiates call via API
        login(client_user)
        call_id = client.post(f"/api/cases/{case_id}/calls").json()["id"]

        # Both sockets should receive incoming call notification
        lawyer_event = lawyer_ws.receive_json()
        assert lawyer_event["type"] == "call_incoming"
        assert lawyer_event["call"]["id"] == call_id

        client_event = client_ws.receive_json()
        assert client_event["type"] == "call_incoming"

        # Client sends WebRTC offer
        offer_sdp = {"type": "offer", "sdp": "v=0\r\no=caller 123 456..."}
        client_ws.send_json({"type": "offer", "call_id": call_id, "sdp": offer_sdp})

        # Lawyer receives offer
        received_offer = lawyer_ws.receive_json()
        assert received_offer["type"] == "offer"
        assert received_offer["call_id"] == call_id
        assert received_offer["sdp"] == offer_sdp
        assert received_offer["from_user_id"] == client_user.id

        # Lawyer sends WebRTC answer
        answer_sdp = {"type": "answer", "sdp": "v=0\r\no=receiver 789 101..."}
        lawyer_ws.send_json({"type": "answer", "call_id": call_id, "sdp": answer_sdp})

        # Client receives answer
        received_answer = client_ws.receive_json()
        assert received_answer["type"] == "answer"
        assert received_answer["call_id"] == call_id
        assert received_answer["sdp"] == answer_sdp

        # ICE candidate trickling
        candidate = {"candidate": "candidate:1 1 UDP 2130706431 192.168.1.1 50000 typ host", "sdpMid": "0"}
        client_ws.send_json({"type": "ice_candidate", "call_id": call_id, "candidate": candidate})

        received_ice = lawyer_ws.receive_json()
        assert received_ice["type"] == "ice_candidate"
        assert received_ice["candidate"] == candidate

    finally:
        _close_ws(client_ws)
        _close_ws(lawyer_ws)


def test_websocket_disconnect_notifies_peer(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    client_ws = _open_call_ws(client, case_id, client_user)
    lawyer_ws = _open_call_ws(client, case_id, lawyer)

    try:
        # Caller unexpectedly closes socket
        _close_ws(client_ws)

        # Lawyer receives peer_disconnected frame
        event = lawyer_ws.receive_json()
        assert event["type"] == "peer_disconnected"
        assert event["user_id"] == client_user.id
        assert event["case_id"] == case_id

    finally:
        _close_ws(lawyer_ws)


def test_stale_abandoned_ringing_call_cleanup(client: TestClient, login):
    client_user, lawyer, case_id = _assigned_case(client, login)

    login(client_user)
    call_id = client.post(f"/api/cases/{case_id}/calls").json()["id"]

    # Age the ringing call past stale timeout
    db = SessionLocal()
    try:
        call = db.get(Call, call_id)
        call.created_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        db.commit()
    finally:
        db.close()

    # Query active call -> triggers auto cleanup to MISSED
    active = client.get(f"/api/cases/{case_id}/calls/active").json()
    assert active["active_call"] is None

    detail = client.get(f"/api/cases/{case_id}/calls/{call_id}").json()
    assert detail["status"] == "MISSED"

    # Now a new call can be initiated without 409 conflict
    new_call = client.post(f"/api/cases/{case_id}/calls")
    assert new_call.status_code == 201
