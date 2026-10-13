from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

# Case practice categories and lifecycle values. Kept as string constants so the
# SQLite test database and PostgreSQL share one definition and migrations can
# spell the allowed values out inline.
CASE_CATEGORIES = (
    "property",
    "family",
    "employment",
    "business",
    "consumer",
    "cybercrime",
    "criminal",
    "immigration",
    "intellectual_property",
    "tax",
    "other",
)
CASE_URGENCIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
CASE_STATUSES = ("OPEN", "ASSIGNED", "COMPLETED", "CLOSED")
CASE_DECISIONS = ("ACCEPT", "REJECT", "REQUEST_INFO")
FEE_PROPOSAL_STATUSES = ("PROPOSED", "ACCEPTED", "DECLINED", "SUPERSEDED")
APPOINTMENT_STATUSES = ("PROPOSED", "CONFIRMED", "CANCELLED")

_CATEGORY_SQL = ", ".join(f"'{value}'" for value in CASE_CATEGORIES)
_URGENCY_SQL = ", ".join(f"'{value}'" for value in CASE_URGENCIES)
_STATUS_SQL = ", ".join(f"'{value}'" for value in CASE_STATUSES)
_DECISION_SQL = ", ".join(f"'{value}'" for value in CASE_DECISIONS)
_FEE_STATUS_SQL = ", ".join(f"'{value}'" for value in FEE_PROPOSAL_STATUSES)
_APPOINTMENT_STATUS_SQL = ", ".join(f"'{value}'" for value in APPOINTMENT_STATUSES)


class Case(Base, TimestampMixin):
    """A legal matter posted by a client for lawyers to browse and accept.

    Only one lawyer may be assigned to a case at a time. Assignment is performed
    with a conditional UPDATE on ``status``/``assigned_lawyer_id`` so two lawyers
    accepting simultaneously cannot both win (see ``app.api.cases``).
    """

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    posted_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    assigned_lawyer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction: Mapped[str | None] = mapped_column(String(128), nullable=True)
    urgency: Mapped[str] = mapped_column(
        String(16), default="MEDIUM", index=True, nullable=False
    )
    consultation_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    budget: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_preference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    client_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default="OPEN", index=True, nullable=False
    )
    # Optional important date / deadline supplied by the client when posting.
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    posted_by: Mapped["User"] = relationship(foreign_keys=[posted_by_user_id])
    assigned_lawyer: Mapped["User | None"] = relationship(
        foreign_keys=[assigned_lawyer_id]
    )
    documents: Mapped[list["CaseDocument"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["CaseDecision"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    activities: Mapped[list["CaseActivity"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    notes: Mapped[list["CaseNote"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    clarifications: Mapped[list["CaseClarificationMessage"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    messages: Mapped[list["CaseMessage"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    fee_proposals: Mapped[list["CaseFeeProposal"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    appointments: Mapped[list["CaseAppointment"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(f"category IN ({_CATEGORY_SQL})", name="ck_cases_category"),
        CheckConstraint(f"urgency IN ({_URGENCY_SQL})", name="ck_cases_urgency"),
        CheckConstraint(f"status IN ({_STATUS_SQL})", name="ck_cases_status"),
    )

    def __repr__(self) -> str:
        return f"<Case id={self.id} status={self.status!r} category={self.category!r}>"


class CaseDocument(Base, TimestampMixin):
    """Links a client document to a case so an assigned lawyer may access it."""

    __tablename__ = "case_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    shared_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    case: Mapped["Case"] = relationship(back_populates="documents")
    document: Mapped["Document"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "case_id", "document_id", name="uq_case_documents_case_document"
        ),
    )


class CaseDecision(Base, TimestampMixin):
    """A lawyer's accept / reject / request-information action on a case."""

    __tablename__ = "case_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    lawyer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    case: Mapped["Case"] = relationship(back_populates="decisions")
    lawyer: Mapped["User"] = relationship(foreign_keys=[lawyer_id])

    __table_args__ = (
        CheckConstraint(
            f"decision IN ({_DECISION_SQL})", name="ck_case_decisions_decision"
        ),
        UniqueConstraint(
            "case_id",
            "lawyer_id",
            "decision",
            name="uq_case_decisions_case_lawyer_decision",
        ),
    )


class CaseActivity(Base, TimestampMixin):
    """Append-only audit trail of actions taken on a case."""

    __tablename__ = "case_activities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(512), nullable=True)

    case: Mapped["Case"] = relationship(back_populates="activities")
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_user_id])


class CaseNote(Base, TimestampMixin):
    """Private working note kept by the assigned lawyer (not shown to clients)."""

    __tablename__ = "case_notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    case: Mapped["Case"] = relationship(back_populates="notes")
    author: Mapped["User | None"] = relationship(foreign_keys=[author_user_id])


class CaseMessage(Base, TimestampMixin):
    """A message in the private workspace between the client and assigned lawyer.

    Only the case's client and its assigned lawyer may read or write these; the
    API enforces that before returning any row. ``read_at`` records when the
    other party first saw the message so unread counts can be derived.
    """

    __tablename__ = "case_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sender_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    case: Mapped["Case"] = relationship(back_populates="messages")
    sender: Mapped["User | None"] = relationship(foreign_keys=[sender_user_id])


class CaseClarificationMessage(Base, TimestampMixin):
    """A question/answer exchanged with the case owner *before* assignment.

    An interested lawyer may ask the client for more information while a case is
    still OPEN and unassigned. Each conversation is a thread identified by
    ``(case_id, lawyer_id)`` and is visible only to that lawyer and the client
    who posted the case; other lawyers can neither read nor post into it. This
    is deliberately separate from :class:`CaseMessage` (the private client /
    assigned-lawyer workspace) so that pre-assignment questions from competing
    lawyers are never disclosed to one another.

    ``read_at`` records when the *recipient* first saw the message so unread
    counts can be derived without an extra table.
    """

    __tablename__ = "case_clarification_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # The lawyer whose thread this is. A thread only ever belongs to one lawyer.
    lawyer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sender_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    case: Mapped["Case"] = relationship(back_populates="clarifications")
    lawyer: Mapped["User"] = relationship(foreign_keys=[lawyer_id])
    sender: Mapped["User | None"] = relationship(foreign_keys=[sender_user_id])

    __table_args__ = (
        Index(
            "ix_case_clarifications_case_lawyer",
            "case_id",
            "lawyer_id",
        ),
    )


class CaseFeeProposal(Base, TimestampMixin):
    """A fee proposal or counteroffer exchanged inside an assigned case.

    A new proposal supersedes the previous open one. Only the *other* party may
    accept or decline an open proposal; the proposer withdraws a proposal by
    making a new one (which supersedes it). Acceptance is final for the case
    until a later proposal reopens it. These rules are enforced server-side.
    """

    __tablename__ = "case_fee_proposals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    proposed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default="PROPOSED", index=True, nullable=False
    )

    case: Mapped["Case"] = relationship(back_populates="fee_proposals")
    proposed_by: Mapped["User | None"] = relationship(foreign_keys=[proposed_by_user_id])

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_FEE_STATUS_SQL})", name="ck_case_fee_proposals_status"
        ),
    )


class CaseAppointment(Base, TimestampMixin):
    """A proposed or confirmed consultation for an assigned case.

    Only the party who did *not* propose a consultation may confirm it, and it
    may only be confirmed while still PROPOSED. Either party may cancel a
    PROPOSED or CONFIRMED consultation. These rules are enforced server-side.
    """

    __tablename__ = "case_appointments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    proposed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default="PROPOSED", index=True, nullable=False
    )

    case: Mapped["Case"] = relationship(back_populates="appointments")
    proposed_by: Mapped["User | None"] = relationship(foreign_keys=[proposed_by_user_id])

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_APPOINTMENT_STATUS_SQL})",
            name="ck_case_appointments_status",
        ),
    )
