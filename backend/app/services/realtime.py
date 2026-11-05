"""In-process realtime hub for the private client / lawyer case workspace.

The private workspace keeps using PostgreSQL as the single source of truth:
messages are always *persisted first* and only then fanned out to the two
authorized parties over WebSockets. The hub is intentionally in-process (a
single uvicorn worker); a horizontally-scaled deployment would need a shared
broker such as Redis pub/sub, which is out of scope here.

Authorization is re-checked on every write (see :func:`persist_message`) rather
than trusted from the connection handshake, so a client that is no longer a
party to the case cannot publish into it.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import WebSocket

from app.core.database import SessionLocal
from app.models import Case, CaseMessage


def display_name(user: Any | None) -> str | None:
    """Human readable label for a message sender (mirrors the HTTP payload)."""

    if user is None:
        return None
    return user.full_name or user.username


def _isoformat(value: Any) -> Any:
    """Return an ISO-8601 string for datetimes so frames stay JSON-serializable."""

    return value.isoformat() if isinstance(value, datetime) else value


def message_public_payload(message: CaseMessage) -> dict[str, Any]:
    """Serialize a workspace message exactly the way the HTTP API does.

    Kept in one place so the REST list endpoint and the WebSocket broadcast can
    never drift apart; the frontend deduplicates on ``id``. Datetimes are
    emitted as ISO strings because WebSocket frames are JSON.
    """

    return {
        "id": message.id,
        "sender_user_id": message.sender_user_id,
        "sender_name": display_name(message.sender),
        "body": message.body,
        "read_at": _isoformat(message.read_at),
        "created_at": _isoformat(message.created_at),
        "updated_at": _isoformat(message.updated_at),
    }


def is_case_party(case: Case, user_id: int) -> bool:
    """True only for the client who posted the case or its assigned lawyer."""

    if case.assigned_lawyer_id is None:
        return False
    return user_id in (case.posted_by_user_id, case.assigned_lawyer_id)


def load_authorized_case(case_id: int, user_id: int) -> Case | None:
    """Return the case iff ``user_id`` is one of its two assigned parties."""

    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        if case is None or not is_case_party(case, user_id):
            return None
        return case
    finally:
        db.close()


def persist_message(case_id: int, user_id: int, body: str) -> dict[str, Any] | None:
    """Persist a workspace message after re-checking authorization.

    Returns the public payload on success, or ``None`` when the sender is no
    longer an authorized party of the case (the caller must then refuse to
    broadcast and should close the connection).
    """

    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        if case is None or not is_case_party(case, user_id):
            return None
        message = CaseMessage(case_id=case_id, sender_user_id=user_id, body=body)
        db.add(message)
        db.commit()
        db.refresh(message)
        return message_public_payload(message)
    finally:
        db.close()


@dataclass(eq=False)
class Connection:
    """A single open WebSocket, keyed by case for broadcast fan-out."""

    websocket: WebSocket
    case_id: int
    user_id: int


class CaseConnectionManager:
    """Tracks live workspace sockets and broadcasts persisted messages.

    ``broadcast_nowait`` lets the synchronous HTTP send path (which runs in a
    threadpool thread) schedule a broadcast onto the server event loop that was
    captured at startup.
    """

    def __init__(self) -> None:
        self._connections: dict[int, set[Connection]] = {}
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(
        self, websocket: WebSocket, case_id: int, user_id: int
    ) -> Connection:
        connection = Connection(websocket=websocket, case_id=case_id, user_id=user_id)
        async with self._lock:
            self._connections.setdefault(case_id, set()).add(connection)
        return connection

    async def disconnect(self, connection: Connection) -> None:
        async with self._lock:
            group = self._connections.get(connection.case_id)
            if group is None:
                return
            group.discard(connection)
            if not group:
                self._connections.pop(connection.case_id, None)

    async def broadcast(self, case_id: int, payload: dict[str, Any]) -> None:
        """Send ``payload`` to every socket watching ``case_id``.

        Sends happen outside the lock so a slow client cannot block others;
        sockets that fail mid-send are pruned.
        """

        async with self._lock:
            targets = list(self._connections.get(case_id, ()))
        stale: list[Connection] = []
        for connection in targets:
            try:
                await connection.websocket.send_json(payload)
            except Exception:
                stale.append(connection)
        for connection in stale:
            await self.disconnect(connection)

    def broadcast_nowait(self, case_id: int, payload: dict[str, Any]) -> None:
        """Thread-safe broadcast for synchronous (threadpool) callers."""

        loop = self._loop
        if loop is None or loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(case_id, payload), loop)

    def count(self, case_id: int) -> int:
        return len(self._connections.get(case_id, ()))


case_connections = CaseConnectionManager()

__all__ = [
    "CaseConnectionManager",
    "Connection",
    "case_connections",
    "display_name",
    "is_case_party",
    "load_authorized_case",
    "message_public_payload",
    "persist_message",
]
