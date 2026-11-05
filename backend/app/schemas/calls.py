from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, Timestamped


class CallRead(ORMModel, Timestamped):
    id: int
    case_id: int
    caller_id: int
    receiver_id: int
    caller_name: str | None = None
    receiver_name: str | None = None
    status: str
    answered_at: datetime | None = None
    ended_at: datetime | None = None
    duration: int | None = None


class CallListResponse(BaseModel):
    items: list[CallRead]
    total: int


class CallActionResponse(BaseModel):
    success: bool
    call: CallRead
    message: str | None = None


class ActiveCallResponse(BaseModel):
    active_call: CallRead | None = None


class WebRTCSignalingMessage(BaseModel):
    type: str = Field(
        ...,
        description="Signaling event type (e.g. auth, offer, answer, ice_candidate, call_accepted, call_rejected, call_ended, ping, pong)",
    )
    call_id: int | None = None
    sdp: Any | None = None
    candidate: Any | None = None
    reason: str | None = None
    data: dict[str, Any] | None = None


__all__ = [
    "ActiveCallResponse",
    "CallActionResponse",
    "CallListResponse",
    "CallRead",
    "WebRTCSignalingMessage",
]

