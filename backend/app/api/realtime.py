"""WebSocket transport for real-time private workspace messaging.

Protocol (all frames are JSON):

Client -> server
    {"type": "auth", "token": "<bearer session token>"}   first frame, required
    {"type": "message", "body": "..."}                    optional send path
    {"type": "ping"}

Server -> client
    {"type": "ready", "case_id": int, "user_id": int}
    {"type": "message", "message": {...CaseMessage...}}
    {"type": "pong"}
    {"type": "error", "code": "..."}

Close codes live in the application range (4xxx):
    4400 malformed auth frame, 4401 missing/invalid token,
    4403 not a party to the case, 4408 auth handshake timed out.

Security: the token is only ever sent in the first frame (never a URL query
string), and authorization is re-evaluated on *every* inbound event, not just
at connect time.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.core.database import SessionLocal
from app.models import User
from app.services.realtime import (
    case_connections,
    load_authorized_case,
    persist_message,
)

router = APIRouter(tags=["realtime"])

AUTH_TIMEOUT_SECONDS = 10.0
MAX_MESSAGE_LENGTH = 5000
SESSION_RECHECK_SECONDS = 15.0

WS_BAD_REQUEST = 4400
WS_UNAUTHORIZED = 4401
WS_FORBIDDEN = 4403
WS_AUTH_TIMEOUT = 4408


def _authenticate(token: str | None) -> User | None:
    """Resolve a token to an active user and detach it from the session."""

    from app.api.deps import authenticate_token

    db = SessionLocal()
    try:
        user = authenticate_token(db, token)
        if user is None:
            return None
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def _validate_session(token: str | None, user_id: int) -> bool:
    """Re-resolve the token and account status for an existing socket."""

    from app.api.deps import authenticate_token, validate_session_token

    db = SessionLocal()
    try:
        if token:
            return validate_session_token(db, token, user_id)
        user = authenticate_token(db, None)
        return user is not None and user.id == user_id
    finally:
        db.close()


async def _watch_session(
    websocket: WebSocket, token: str | None, user_id: int
) -> None:
    """Close a connection when its session expires or the account is disabled."""

    try:
        while True:
            await asyncio.sleep(SESSION_RECHECK_SECONDS)
            if not await run_in_threadpool(_validate_session, token, user_id):
                await websocket.close(code=WS_UNAUTHORIZED)
                return
    except asyncio.CancelledError:
        raise
    except Exception:
        return


def _extract_token(raw: str) -> tuple[bool, str | None]:
    """Return ``(is_auth_frame, token)`` for the first client frame."""

    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return False, None
    if not isinstance(data, dict) or data.get("type") != "auth":
        return False, None
    token = data.get("token")
    return True, token if isinstance(token, str) and token else None


async def _send(websocket: WebSocket, payload: dict[str, Any]) -> bool:
    try:
        await websocket.send_json(payload)
        return True
    except Exception:
        return False


async def _handle_event(
    websocket: WebSocket,
    case_id: int,
    user_id: int,
    token: str | None,
    raw: str,
) -> int | None:
    """Handle one inbound frame. Returns a close code when the socket must close."""

    if not await run_in_threadpool(_validate_session, token, user_id):
        await _send(websocket, {"type": "error", "code": "session_invalid"})
        return WS_UNAUTHORIZED

    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        await _send(websocket, {"type": "error", "code": "invalid_payload"})
        return None
    if not isinstance(data, dict):
        await _send(websocket, {"type": "error", "code": "invalid_payload"})
        return None

    event = data.get("type")
    if event == "ping":
        await _send(websocket, {"type": "pong"})
        return None

    if event in {"message", "send"}:
        body = data.get("body")
        body = body.strip() if isinstance(body, str) else ""
        if not body:
            await _send(websocket, {"type": "error", "code": "empty_message"})
            return None
        if len(body) > MAX_MESSAGE_LENGTH:
            await _send(websocket, {"type": "error", "code": "message_too_long"})
            return None
        # Authorization is re-checked inside persist_message for every event.
        payload = await run_in_threadpool(persist_message, case_id, user_id, body)
        if payload is None:
            await _send(websocket, {"type": "error", "code": "not_authorized"})
            return WS_FORBIDDEN
        await case_connections.broadcast(
            case_id, {"type": "message", "message": payload}
        )
        return None

    await _send(websocket, {"type": "error", "code": "unknown_event"})
    return None


@router.websocket("/cases/{case_id}/ws")
async def case_workspace_socket(websocket: WebSocket, case_id: int) -> None:
    await websocket.accept()

    try:
        raw = await asyncio.wait_for(
            websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        await websocket.close(code=WS_AUTH_TIMEOUT)
        return
    except WebSocketDisconnect:
        return

    is_auth, token = _extract_token(raw)
    if not is_auth:
        await websocket.close(code=WS_BAD_REQUEST)
        return

    user = await run_in_threadpool(_authenticate, token)
    if user is None:
        await websocket.close(code=WS_UNAUTHORIZED)
        return

    case = await run_in_threadpool(load_authorized_case, case_id, user.id)
    if case is None:
        await websocket.close(code=WS_FORBIDDEN)
        return

    connection = await case_connections.connect(websocket, case_id, user.id)
    await _send(
        websocket, {"type": "ready", "case_id": case_id, "user_id": user.id}
    )
    watcher = asyncio.create_task(_watch_session(websocket, token, user.id))

    try:
        while True:
            raw = await websocket.receive_text()
            close_code = await _handle_event(
                websocket, case_id, user.id, token, raw
            )
            if close_code is not None:
                await websocket.close(code=close_code)
                break
    except WebSocketDisconnect:
        pass
    finally:
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass
        await case_connections.disconnect(connection)


__all__ = ["router"]
