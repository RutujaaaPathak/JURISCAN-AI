from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.case import CASE_CATEGORIES, CASE_URGENCIES
from app.schemas.common import ORMModel, Timestamped


class CaseCreate(ORMModel):
    title: str = Field(min_length=3, max_length=255)
    category: str = Field(min_length=1, max_length=32)
    summary: str = Field(min_length=10, max_length=5000)
    jurisdiction: str | None = Field(default=None, max_length=128)
    urgency: str = Field(default="MEDIUM", max_length=16)
    consultation_method: str | None = Field(default=None, max_length=32)
    budget: str | None = Field(default=None, max_length=128)
    contact_preference: str | None = Field(default=None, max_length=128)
    client_reference: str | None = Field(default=None, max_length=64)
    # Optional important date / deadline for the matter.
    deadline: datetime | None = None
    # Documents owned by the posting user to attach to the case. Ownership is
    # verified server-side; unknown or unowned ids are rejected.
    document_ids: list[int] = Field(default_factory=list)

    @field_validator("category")
    @classmethod
    def _valid_category(cls, value: str) -> str:
        lowered = value.strip().lower()
        if lowered not in CASE_CATEGORIES:
            raise ValueError(f"Unsupported category: {value}")
        return lowered

    @field_validator("urgency")
    @classmethod
    def _valid_urgency(cls, value: str) -> str:
        upper = value.strip().upper()
        if upper not in CASE_URGENCIES:
            raise ValueError(f"Unsupported urgency: {value}")
        return upper


class CaseDecisionCreate(ORMModel):
    reason: str | None = Field(default=None, max_length=2000)
    message: str | None = Field(default=None, max_length=5000)


class CaseNoteCreate(ORMModel):
    body: str = Field(min_length=1, max_length=5000)


class CaseDocumentSummary(ORMModel):
    id: int
    document_id: int
    title: str
    filename: str
    file_type: str
    status: str
    risk_score: float | None = None
    risk_level: str | None = None
    shared_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime


class CaseDecisionRead(ORMModel, Timestamped):
    id: int
    lawyer_id: int
    lawyer_name: str | None = None
    decision: str
    reason: str | None = None
    message: str | None = None


class CaseActivityRead(ORMModel, Timestamped):
    id: int
    action: str
    detail: str | None = None
    actor_user_id: int | None = None
    actor_name: str | None = None


class CaseNoteRead(ORMModel, Timestamped):
    id: int
    body: str
    author_user_id: int | None = None
    author_name: str | None = None


class CaseSummary(ORMModel):
    id: int
    title: str
    category: str
    summary: str
    jurisdiction: str | None = None
    urgency: str
    consultation_method: str | None = None
    budget: str | None = None
    contact_preference: str | None = None
    client_reference: str | None = None
    status: str
    posted_by_user_id: int
    posted_by_name: str | None = None
    assigned_lawyer_id: int | None = None
    assigned_lawyer_name: str | None = None
    document_count: int = 0
    decision_count: int = 0
    my_decision: str | None = None
    deadline: datetime | None = None
    created_at: datetime
    updated_at: datetime
    accepted_at: datetime | None = None
    completed_at: datetime | None = None


class CaseDetail(CaseSummary):
    documents: list[CaseDocumentSummary] = Field(default_factory=list)
    decisions: list[CaseDecisionRead] = Field(default_factory=list)
    activities: list[CaseActivityRead] = Field(default_factory=list)
    # Private working notes are only returned to the assigned lawyer.
    notes: list[CaseNoteRead] = Field(default_factory=list)


class CaseListResponse(BaseModel):
    items: list[CaseSummary]
    total: int


class MyCasesResponse(BaseModel):
    active: list[CaseSummary] = Field(default_factory=list)
    completed: list[CaseSummary] = Field(default_factory=list)
    pending: list[CaseSummary] = Field(default_factory=list)
    declined: list[CaseSummary] = Field(default_factory=list)


class CaseCategoryCount(BaseModel):
    category: str
    count: int


class LawyerOverview(BaseModel):
    available_cases: int
    pending_requests: int
    active_cases: int
    completed_cases: int
    total_handled: int
    unread_messages: int
    case_status_distribution: dict[str, int]
    case_category_distribution: list[CaseCategoryCount]


class ClientOverview(BaseModel):
    submitted_cases: int
    open_requests: int
    active_matters: int
    completed_matters: int
    upcoming_consultations: int
    unread_messages: int
    case_status_distribution: dict[str, int]
    case_category_distribution: list[CaseCategoryCount]


class CaseMessageCreate(ORMModel):
    body: str = Field(min_length=1, max_length=5000)


class CaseMessageRead(ORMModel, Timestamped):
    id: int
    sender_user_id: int | None = None
    sender_name: str | None = None
    body: str
    read_at: datetime | None = None


class CaseMessageListResponse(BaseModel):
    items: list[CaseMessageRead] = Field(default_factory=list)
    unread: int = 0


class CaseClarificationCreate(ORMModel):
    message: str = Field(min_length=1, max_length=5000)
    # Required when the case owner replies, so the API knows which lawyer's
    # thread is being answered. Ignored for a lawyer (their own id is used).
    lawyer_id: int | None = None


class CaseClarificationRead(ORMModel, Timestamped):
    id: int
    lawyer_id: int
    sender_user_id: int | None = None
    sender_name: str | None = None
    body: str
    read_at: datetime | None = None


class CaseClarificationThread(ORMModel):
    lawyer_id: int
    lawyer_name: str | None = None
    unread: int = 0
    items: list[CaseClarificationRead] = Field(default_factory=list)


class CaseClarificationThreadsResponse(BaseModel):
    threads: list[CaseClarificationThread] = Field(default_factory=list)


class CaseClarificationReadMark(ORMModel):
    lawyer_id: int | None = None


class CaseDocumentAttach(ORMModel):
    document_id: int


class CaseFeeProposalCreate(ORMModel):
    amount: str = Field(min_length=1, max_length=64)
    currency: str = Field(default="INR", max_length=8)
    note: str | None = Field(default=None, max_length=2000)


class CaseFeeProposalRead(ORMModel, Timestamped):
    id: int
    proposed_by_user_id: int | None = None
    proposed_by_name: str | None = None
    amount: str
    currency: str
    note: str | None = None
    status: str


class CaseAppointmentCreate(ORMModel):
    scheduled_at: datetime
    duration_minutes: int | None = Field(default=None, ge=5, le=600)
    mode: str | None = Field(default=None, max_length=32)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class CaseAppointmentRead(ORMModel, Timestamped):
    id: int
    proposed_by_user_id: int | None = None
    proposed_by_name: str | None = None
    scheduled_at: datetime
    duration_minutes: int | None = None
    mode: str | None = None
    location: str | None = None
    notes: str | None = None
    status: str


class NotificationRead(BaseModel):
    id: str
    kind: str
    title: str
    detail: str | None = None
    case_id: int | None = None
    created_at: datetime
