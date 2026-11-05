from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.user import User

CALL_STATUSES = ("RINGING", "ACCEPTED", "REJECTED", "MISSED", "ENDED", "FAILED")
ACTIVE_CALL_STATUSES = ("RINGING", "ACCEPTED")
TERMINAL_CALL_STATUSES = ("REJECTED", "MISSED", "ENDED", "FAILED")

_STATUS_SQL = ", ".join(f"'{s}'" for s in CALL_STATUSES)


class Call(Base, TimestampMixin):
    """A real-time browser-to-browser voice call between a client and assigned lawyer.

    Only one active call (status RINGING or ACCEPTED) is permitted per case at
    any given time, guaranteed by a partial unique index and transaction-level
    validation. Audio communication is handled peer-to-peer over WebRTC and is
    never transmitted or stored on the backend.
    """

    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    caller_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    receiver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), default="RINGING", index=True, nullable=False
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)

    case: Mapped["Case"] = relationship(back_populates="calls")
    caller: Mapped["User"] = relationship(foreign_keys=[caller_id])
    receiver: Mapped["User"] = relationship(foreign_keys=[receiver_id])

    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUS_SQL})", name="ck_calls_status"),
        CheckConstraint(
            "caller_id <> receiver_id", name="ck_calls_caller_receiver_distinct"
        ),
        CheckConstraint(
            "duration IS NULL OR duration >= 0",
            name="ck_calls_duration_non_negative",
        ),
        Index(
            "ix_calls_active_case",
            "case_id",
            unique=True,
            postgresql_where=text("status IN ('RINGING', 'ACCEPTED')"),
            sqlite_where=text("status IN ('RINGING', 'ACCEPTED')"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Call id={self.id} case_id={self.case_id} status={self.status!r}>"


__all__ = [
    "ACTIVE_CALL_STATUSES",
    "CALL_STATUSES",
    "Call",
    "TERMINAL_CALL_STATUSES",
]

