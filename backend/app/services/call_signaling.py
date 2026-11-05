"""In-process WebRTC signaling hub for real-time browser-to-browser voice calling.

This hub manages dedicated WebSocket connections for voice call invitations,
SDP offer/answer exchanges, and ICE candidates between the case owner and
currently assigned lawyer.

No audio data is ever transmitted, routed, or stored through this service or backend.
WebRTC handles audio communication peer-to-peer directly between browsers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import SessionLocal
from app.models import Call, Case, User
from app.services.realtime import display_name


def _isoformat(value: Any) -> Any:
    """Return an ISO-8601 string for datetimes so JSON WebSocket frames are valid."""
    return value.isoformat() if isinstance(value, datetime) else value


def calculate_duration(start: datetime | None, end: datetime | None) -> int:
    """Safely calculate non-negative duration in seconds between two timestamps."""
    if not start or not end:
        return 0
    if start.tzinfo is None and end.tzinfo is not None:
        start = start.replace(tzinfo=timezone.utc)
    elif start.tzinfo is not None and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return max(0, int((end - start).total_seconds()))


def call_public_payload(call: Call) -> dict[str, Any]:
    """Serialize a Call model into the standard JSON-safe dictionary representation."""
    caller_name = None
    receiver_name = None
    try:
        caller_name = display_name(call.caller)
    except Exception:
        pass
    try:
        receiver_name = display_name(call.receiver)
    except Exception:
        pass

    return {
        "id": call.id,
        "case_id": call.case_id,
        "caller_id": call.caller_id,
        "receiver_id": call.receiver_id,
        "caller_name": caller_name,
        "receiver_name": receiver_name,
        "status": call.status,
        "answered_at": _isoformat(call.answered_at),
        "ended_at": _isoformat(call.ended_at),
        "duration": call.duration,
        "created_at": _isoformat(call.created_at),
        "updated_at": _isoformat(call.updated_at),
    }


def is_case_call_party(case: Case, user_id: int) -> bool:
    """True only if the case has an assigned lawyer and user_id is the client or assigned lawyer."""
    if case.assigned_lawyer_id is None:
        return False
    return user_id in (case.posted_by_user_id, case.assigned_lawyer_id)


def load_call_authorized_case(case_id: int, user_id: int) -> Case | None:
    """Return the Case if user_id is authorized to participate in calls for it."""
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        if case is None or not is_case_call_party(case, user_id):
            return None
        return case
    finally:
        db.close()


def load_call_with_participants(db, call_id: int, case_id: int | None = None) -> Call | None:
    """Load a Call with caller and receiver eager loaded."""
    stmt = (
        select(Call)
        .options(selectinload(Call.caller), selectinload(Call.receiver))
        .where(Call.id == call_id)
    )
    if case_id is not None:
        stmt = stmt.where(Call.case_id == case_id)
    return db.scalar(stmt)


def handle_participant_disconnect(case_id: int, user_id: int) -> dict[str, Any] | None:
    """Safely handle participant disconnection for active calls.

    If a ringing call was initiated by the disconnecting user, mark it MISSED.
    If an accepted call loses a participant, return details for notification.
    """
    db = SessionLocal()
    try:
        stmt = (
            select(Call)
            .options(selectinload(Call.caller), selectinload(Call.receiver))
            .where(
                Call.case_id == case_id,
                Call.status.in_(["RINGING", "ACCEPTED"]),
            )
            .order_by(Call.created_at.desc())
        )
        active_call = db.scalar(stmt)
        if not active_call:
            return None

        now = datetime.now(timezone.utc)
        if active_call.status == "RINGING" and active_call.caller_id == user_id:
            # Caller abandoned while ringing
            active_call.status = "MISSED"
            active_call.ended_at = now
            active_call.duration = 0
            db.commit()
            db.refresh(active_call)
            return call_public_payload(active_call)

        return None
    finally:
        db.close()


@dataclass(eq=False)
class CallConnection:
    """A live WebSocket connection for WebRTC signaling."""

    websocket: WebSocket
    case_id: int
    user_id: int


class CallSignalingManager:
    """In-memory signaling coordinator for voice call WebSockets."""

    def __init__(self) -> None:
        self._connections: dict[int, set[CallConnection]] = {}
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(
        self, websocket: WebSocket, case_id: int, user_id: int
    ) -> CallConnection:
        conn = CallConnection(websocket=websocket, case_id=case_id, user_id=user_id)
        async with self._lock:
            self._connections.setdefault(case_id, set()).add(conn)
        return conn

    async def disconnect(self, conn: CallConnection) -> None:
        async with self._lock:
            group = self._connections.get(conn.case_id)
            if group is not None:
                group.discard(conn)
                if not group:
                    self._connections.pop(conn.case_id, None)

    async def send_to_user(
        self, case_id: int, target_user_id: int, payload: dict[str, Any]
    ) -> None:
        """Send a signaling frame to all active sockets of a specific user."""
        async with self._lock:
            group = list(self._connections.get(case_id, ()))
        targets = [c for c in group if c.user_id == target_user_id]
        stale: list[CallConnection] = []
        for c in targets:
            try:
                await c.websocket.send_json(payload)
            except Exception:
                stale.append(c)
        for c in stale:
            await self.disconnect(c)

    async def send_to_peer(
        self, case_id: int, sender_user_id: int, payload: dict[str, Any]
    ) -> None:
        """Send a signaling frame to all sockets in the case except the sender."""
        async with self._lock:
            group = list(self._connections.get(case_id, ()))
        peers = [c for c in group if c.user_id != sender_user_id]
        stale: list[CallConnection] = []
        for c in peers:
            try:
                await c.websocket.send_json(payload)
            except Exception:
                stale.append(c)
        for c in stale:
            await self.disconnect(c)

    async def broadcast(self, case_id: int, payload: dict[str, Any]) -> None:
        """Send a payload to all connected sockets for this case."""
        async with self._lock:
            targets = list(self._connections.get(case_id, ()))
        stale: list[CallConnection] = []
        for c in targets:
            try:
                await c.websocket.send_json(payload)
            except Exception:
                stale.append(c)
        for c in stale:
            await self.disconnect(c)

    def broadcast_nowait(self, case_id: int, payload: dict[str, Any]) -> None:
        """Schedule a broadcast from synchronous HTTP threads."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(case_id, payload), loop)

    def send_to_peer_nowait(
        self, case_id: int, sender_user_id: int, payload: dict[str, Any]
    ) -> None:
        """Schedule a peer send from synchronous HTTP threads."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(
            self.send_to_peer(case_id, sender_user_id, payload), loop
        )

    def has_user_connections(self, case_id: int, user_id: int) -> bool:
        """Check if user_id currently has any open connections for case_id."""
        group = self._connections.get(case_id, set())
        return any(c.user_id == user_id for c in group)

    def count(self, case_id: int) -> int:
        return len(self._connections.get(case_id, ()))


call_signaling_manager = CallSignalingManager()

__all__ = [
    "CallConnection",
    "CallSignalingManager",
    "calculate_duration",
    "call_public_payload",
    "call_signaling_manager",
    "handle_participant_disconnect",
    "is_case_call_party",
    "load_call_authorized_case",
    "load_call_with_participants",
]
