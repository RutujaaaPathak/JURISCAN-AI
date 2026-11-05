"""REST and WebSocket APIs for real-time voice calls.

Case owners and their assigned lawyers can initiate, accept, reject, and end calls,
review call history, and exchange WebRTC signaling messages (offers, answers, and
ICE candidates).

Audio is handled peer-to-peer over WebRTC in the browser and is never stored or
relayed through this service. Authentication tokens are passed in the first WebSocket
JSON frame rather than the URL query string.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from starlette.concurrency import run_in_threadpool

from app.api.deps import CurrentUser, DbSession
from app.core.database import SessionLocal
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationFailed,
)
from app.models import Call, Case, User
from app.schemas.calls import (
    ActiveCallResponse,
    CallListResponse,
    CallRead,
)
from app.services.call_signaling import (
    calculate_duration,
    call_public_payload,
    call_signaling_manager,
    is_case_call_party,
    load_call_authorized_case,
    load_call_with_participants,
)

router = APIRouter(tags=["calls"])

AUTH_TIMEOUT_SECONDS = 10.0
RINGING_STALE_TIMEOUT_SECONDS = 60

WS_BAD_REQUEST = 4400
WS_UNAUTHORIZED = 4401
WS_FORBIDDEN = 4403
WS_AUTH_TIMEOUT = 4408


def _cleanup_stale_calls(db: Session, case_id: int) -> None:
    """Auto-transition abandoned ringing calls to MISSED."""
    now = datetime.now(timezone.utc)
    ringing_calls = db.scalars(
        select(Call).where(Call.case_id == case_id, Call.status == "RINGING")
    ).all()
    changed = False
    for call in ringing_calls:
        dur = calculate_duration(call.created_at, now)
        if dur >= RINGING_STALE_TIMEOUT_SECONDS:
            call.status = "MISSED"
            call.ended_at = now
            call.duration = 0
            changed = True
    if changed:
        db.commit()


def _get_authorized_case(db: DbSession, case_id: int, user: User) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError("Case not found.")
    if not is_case_call_party(case, user.id):
        if case.assigned_lawyer_id is None:
            raise ConflictError("Cannot initiate or participate in calls: no lawyer is assigned to this case.")
        raise ForbiddenError("You are not authorized to participate in calls for this case.")
    return case


@router.post("/cases/{case_id}/calls", status_code=201, response_model=CallRead)
def initiate_call(case_id: int, db: DbSession, user: CurrentUser):
    """Initiate a voice call to the other assigned party for this case."""
    case = _get_authorized_case(db, case_id, user)

    # Clean any stale abandoned ringing calls first
    _cleanup_stale_calls(db, case_id)

    # Determine caller and receiver
    if user.id == case.posted_by_user_id:
        receiver_id = case.assigned_lawyer_id
    else:
        receiver_id = case.posted_by_user_id

    if receiver_id is None:
        raise ConflictError("Cannot initiate a call: no lawyer is assigned to this case.")

    # Check for active call
    active_stmt = select(Call).where(
        Call.case_id == case_id,
        Call.status.in_(["RINGING", "ACCEPTED"]),
    )
    if db.bind.dialect.name == "postgresql":
        active_stmt = active_stmt.with_for_update()

    existing_active = db.scalar(active_stmt)
    if existing_active is not None:
        raise ConflictError("An active call is already in progress for this case.")

    call = Call(
        case_id=case_id,
        caller_id=user.id,
        receiver_id=receiver_id,
        status="RINGING",
    )
    db.add(call)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("An active call is already in progress for this case.")

    call = load_call_with_participants(db, call.id, case_id)
    payload = call_public_payload(call)
    call_signaling_manager.broadcast_nowait(
        case_id, {"type": "call_incoming", "call": payload}
    )
    return payload


@router.get("/cases/{case_id}/calls", response_model=CallListResponse)
def get_call_history(
    case_id: int,
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Retrieve call history for this case."""
    _get_authorized_case(db, case_id, user)
    _cleanup_stale_calls(db, case_id)

    total = db.scalar(
        select(func.count(Call.id)).where(Call.case_id == case_id)
    ) or 0

    stmt = (
        select(Call)
        .options(selectinload(Call.caller), selectinload(Call.receiver))
        .where(Call.case_id == case_id)
        .order_by(Call.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    calls = db.scalars(stmt).all()
    items = [call_public_payload(c) for c in calls]
    return {"items": items, "total": total}


@router.get("/cases/{case_id}/calls/active", response_model=ActiveCallResponse)
def get_active_call(case_id: int, db: DbSession, user: CurrentUser):
    """Retrieve the current active call for this case, if any."""
    _get_authorized_case(db, case_id, user)
    _cleanup_stale_calls(db, case_id)

    stmt = (
        select(Call)
        .options(selectinload(Call.caller), selectinload(Call.receiver))
        .where(
            Call.case_id == case_id,
            Call.status.in_(["RINGING", "ACCEPTED"]),
        )
        .order_by(Call.created_at.desc())
    )
    active = db.scalar(stmt)
    return {"active_call": call_public_payload(active) if active else None}


@router.get("/cases/{case_id}/calls/{call_id}", response_model=CallRead)
def get_call_detail(case_id: int, call_id: int, db: DbSession, user: CurrentUser):
    """Retrieve details for a specific call."""
    _get_authorized_case(db, case_id, user)

    call = load_call_with_participants(db, call_id, case_id)
    if call is None:
        raise NotFoundError("Call not found.")
    return call_public_payload(call)


@router.post("/cases/{case_id}/calls/{call_id}/accept", response_model=CallRead)
def accept_call(case_id: int, call_id: int, db: DbSession, user: CurrentUser):
    """Accept an incoming ringing call."""
    _get_authorized_case(db, case_id, user)

    stmt = select(Call).where(Call.id == call_id, Call.case_id == case_id)
    if db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()

    call = db.scalar(stmt)
    if call is None:
        raise NotFoundError("Call not found.")

    if user.id != call.receiver_id:
        if user.id == call.caller_id:
            raise ForbiddenError("The caller cannot accept their own call.")
        raise ForbiddenError("You are not the receiver of this call.")

    if call.status != "RINGING":
        raise ConflictError(f"Cannot accept call in '{call.status}' state.")

    now = datetime.now(timezone.utc)
    call.status = "ACCEPTED"
    call.answered_at = now
    db.commit()

    call = load_call_with_participants(db, call.id, case_id)
    payload = call_public_payload(call)
    call_signaling_manager.broadcast_nowait(
        case_id, {"type": "call_accepted", "call": payload}
    )
    return payload


@router.post("/cases/{case_id}/calls/{call_id}/reject", response_model=CallRead)
def reject_call(
    case_id: int,
    call_id: int,
    db: DbSession,
    user: CurrentUser,
    reason: str | None = Query(default=None),
):
    """Reject an incoming ringing call."""
    _get_authorized_case(db, case_id, user)

    stmt = select(Call).where(Call.id == call_id, Call.case_id == case_id)
    if db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()

    call = db.scalar(stmt)
    if call is None:
        raise NotFoundError("Call not found.")

    if user.id not in (call.receiver_id, call.caller_id):
        raise ForbiddenError("You are not a participant in this call.")

    if call.status != "RINGING":
        raise ConflictError(f"Cannot reject call in '{call.status}' state.")

    now = datetime.now(timezone.utc)
    call.ended_at = now
    call.duration = 0
    # If the receiver rejects it is REJECTED; if caller cancels it is MISSED
    call.status = "REJECTED" if user.id == call.receiver_id else "MISSED"
    db.commit()

    call = load_call_with_participants(db, call.id, case_id)
    payload = call_public_payload(call)
    call_signaling_manager.broadcast_nowait(
        case_id, {"type": "call_rejected", "call": payload, "reason": reason}
    )
    return payload


@router.post("/cases/{case_id}/calls/{call_id}/end", response_model=CallRead)
def end_call(
    case_id: int,
    call_id: int,
    db: DbSession,
    user: CurrentUser,
    reason: str | None = Query(default=None),
):
    """End an active or ringing call."""
    _get_authorized_case(db, case_id, user)

    stmt = select(Call).where(Call.id == call_id, Call.case_id == case_id)
    if db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()

    call = db.scalar(stmt)
    if call is None:
        raise NotFoundError("Call not found.")

    if user.id not in (call.caller_id, call.receiver_id):
        raise ForbiddenError("You are not a participant in this call.")

    if call.status in ("ENDED", "REJECTED", "MISSED", "FAILED"):
        raise ConflictError(f"Call is already in terminal state '{call.status}'.")

    now = datetime.now(timezone.utc)
    call.ended_at = now

    if call.status == "ACCEPTED":
        call.status = "ENDED"
        call.duration = calculate_duration(call.answered_at, now)
    elif call.status == "RINGING":
        call.status = "MISSED" if user.id == call.caller_id else "REJECTED"
        call.duration = 0

    db.commit()

    call = load_call_with_participants(db, call.id, case_id)
    payload = call_public_payload(call)
    call_signaling_manager.broadcast_nowait(
        case_id, {"type": "call_ended", "call": payload, "reason": reason}
    )
    return payload


# -----------------------------------------------------------------------------
# WebSocket Signaling Endpoint
# -----------------------------------------------------------------------------


def _authenticate_ws(token: str | None) -> User | None:
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


def _extract_ws_token(raw: str) -> tuple[bool, str | None]:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return False, None
    if not isinstance(data, dict) or data.get("type") != "auth":
        return False, None
    token = data.get("token")
    return True, token if isinstance(token, str) and token else None


def _validate_call_participant(case_id: int, call_id: int | None, user_id: int) -> bool:
    if call_id is None:
        return False
    db = SessionLocal()
    try:
        call = db.get(Call, call_id)
        if call is None or call.case_id != case_id:
            return False
        return user_id in (call.caller_id, call.receiver_id)
    finally:
        db.close()


def _safe_end_call(case_id: int, call_id: int, user_id: int) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        call = db.get(Call, call_id)
        if not call or call.case_id != case_id or user_id not in (call.caller_id, call.receiver_id):
            return None
        if call.status in ("ENDED", "REJECTED", "MISSED", "FAILED"):
            return call_public_payload(call)

        now = datetime.now(timezone.utc)
        call.ended_at = now
        if call.status == "ACCEPTED":
            call.status = "ENDED"
            call.duration = calculate_duration(call.answered_at, now)
        elif call.status == "RINGING":
            call.status = "MISSED" if user_id == call.caller_id else "REJECTED"
            call.duration = 0

        db.commit()
        call = load_call_with_participants(db, call.id, case_id)
        return call_public_payload(call)
    finally:
        db.close()


async def _handle_signaling_event(
    websocket: WebSocket, case_id: int, user_id: int, raw: str
) -> bool:
    """Handle one signaling frame. Returns False when socket must close."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        await websocket.send_json({"type": "error", "code": "invalid_payload"})
        return True

    if not isinstance(data, dict):
        await websocket.send_json({"type": "error", "code": "invalid_payload"})
        return True

    # Re-evaluate case authorization on every single inbound event
    authorized_case = await run_in_threadpool(load_call_authorized_case, case_id, user_id)
    if authorized_case is None:
        await websocket.send_json({"type": "error", "code": "not_authorized"})
        return False

    event_type = data.get("type")

    if event_type == "ping":
        await websocket.send_json({"type": "pong"})
        return True

    if event_type in ("offer", "answer", "ice_candidate"):
        call_id = data.get("call_id")
        is_participant = await run_in_threadpool(
            _validate_call_participant, case_id, call_id, user_id
        )
        if not is_participant:
            await websocket.send_json({"type": "error", "code": "forbidden_call"})
            return True

        # Forward signaling payload directly to the peer
        payload = {
            "type": event_type,
            "call_id": call_id,
            "from_user_id": user_id,
        }
        if event_type in ("offer", "answer"):
            payload["sdp"] = data.get("sdp")
        elif event_type == "ice_candidate":
            payload["candidate"] = data.get("candidate")

        await call_signaling_manager.send_to_peer(case_id, user_id, payload)
        return True

    if event_type == "call_hangup":
        call_id = data.get("call_id")
        if isinstance(call_id, int):
            ended_payload = await run_in_threadpool(_safe_end_call, case_id, call_id, user_id)
            if ended_payload:
                await call_signaling_manager.broadcast(
                    case_id, {"type": "call_ended", "call": ended_payload}
                )
        return True

    await websocket.send_json({"type": "error", "code": "unknown_event"})
    return True


@router.websocket("/cases/{case_id}/calls/ws")
async def call_signaling_socket(websocket: WebSocket, case_id: int) -> None:
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

    is_auth, token = _extract_ws_token(raw)
    if not is_auth:
        await websocket.close(code=WS_BAD_REQUEST)
        return

    user = await run_in_threadpool(_authenticate_ws, token)
    if user is None:
        await websocket.close(code=WS_UNAUTHORIZED)
        return

    case = await run_in_threadpool(load_call_authorized_case, case_id, user.id)
    if case is None:
        await websocket.close(code=WS_FORBIDDEN)
        return

    conn = await call_signaling_manager.connect(websocket, case_id, user.id)
    await websocket.send_json({"type": "ready", "case_id": case_id, "user_id": user.id})

    try:
        while True:
            raw = await websocket.receive_text()
            keep_open = await _handle_signaling_event(websocket, case_id, user.id, raw)
            if not keep_open:
                await websocket.close(code=WS_FORBIDDEN)
                break
    except WebSocketDisconnect:
        pass
    finally:
        await call_signaling_manager.disconnect(conn)
        await call_signaling_manager.send_to_peer(
            case_id,
            user.id,
            {"type": "peer_disconnected", "user_id": user.id, "case_id": case_id},
        )


__all__ = ["router"]
