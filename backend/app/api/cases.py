"""Case browsing and the lawyer accept / reject / request-info workflow.

Authorization note: every endpoint derives its principal from
``app.api.deps.get_current_user``. That function currently resolves to a single
default workspace user because authentication is not implemented yet, and role
checks run against ``User.role`` (optionally overridden by a development-only
header). The checks themselves are real and server-side, but they are only as
trustworthy as the authentication layer that does not exist yet.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, LawyerUser
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationFailed,
)
from app.models import (
    CASE_CATEGORIES,
    CASE_URGENCIES,
    Analysis,
    Case,
    CaseActivity,
    CaseAppointment,
    CaseClarificationMessage,
    CaseDecision,
    CaseDocument,
    CaseFeeProposal,
    CaseMessage,
    CaseNote,
    Document,
    User,
)
from app.schemas.cases import (
    CaseAppointmentCreate,
    CaseAppointmentRead,
    CaseClarificationCreate,
    CaseClarificationReadMark,
    CaseClarificationThreadsResponse,
    CaseCreate,
    CaseDecisionCreate,
    CaseDetail,
    CaseDocumentAttach,
    CaseFeeProposalCreate,
    CaseFeeProposalRead,
    CaseListResponse,
    CaseMessageCreate,
    CaseMessageListResponse,
    CaseNoteCreate,
    ClientOverview,
    LawyerOverview,
    MyCasesResponse,
    NotificationRead,
)

router = APIRouter(tags=["cases"])

URGENCY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
ACTIVE_STATUSES = ("ASSIGNED",)
COMPLETED_STATUSES = ("COMPLETED", "CLOSED")


def _display_name(user: User | None) -> str | None:
    if user is None:
        return None
    return user.full_name or user.username


def _risk_band(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def _latest_analysis(document: Document) -> Analysis | None:
    if not document.analyses:
        return None
    return max(document.analyses, key=lambda analysis: (analysis.created_at, analysis.id))


def _case_query():
    return select(Case).options(
        selectinload(Case.posted_by),
        selectinload(Case.assigned_lawyer),
        selectinload(Case.documents)
        .selectinload(CaseDocument.document)
        .selectinload(Document.analyses),
        selectinload(Case.decisions).selectinload(CaseDecision.lawyer),
        selectinload(Case.activities).selectinload(CaseActivity.actor),
        selectinload(Case.notes).selectinload(CaseNote.author),
    )


def _load_case(db: DbSession, case_id: int) -> Case | None:
    return db.scalar(
        _case_query().where(Case.id == case_id).execution_options(populate_existing=True)
    )


def _decided_case_ids(user_id: int):
    return select(CaseDecision.case_id).where(CaseDecision.lawyer_id == user_id)


def _my_latest_decision(case: Case, user_id: int) -> CaseDecision | None:
    mine = [decision for decision in case.decisions if decision.lawyer_id == user_id]
    if not mine:
        return None
    return max(mine, key=lambda decision: (decision.created_at, decision.id))


def _document_payload(link: CaseDocument) -> dict:
    document = link.document
    analysis = _latest_analysis(document)
    score = analysis.risk_score if analysis else None
    return {
        "id": link.id,
        "document_id": link.document_id,
        "title": document.title,
        "filename": document.filename,
        "file_type": document.file_type,
        "status": document.status,
        "risk_score": score,
        "risk_level": _risk_band(score),
        "shared_by_user_id": link.shared_by_user_id,
        "created_at": link.created_at,
        "updated_at": link.updated_at,
    }


def _decision_payload(decision: CaseDecision) -> dict:
    return {
        "id": decision.id,
        "lawyer_id": decision.lawyer_id,
        "lawyer_name": _display_name(decision.lawyer),
        "decision": decision.decision,
        "reason": decision.reason,
        "message": decision.message,
        "created_at": decision.created_at,
        "updated_at": decision.updated_at,
    }


def _activity_payload(activity: CaseActivity) -> dict:
    return {
        "id": activity.id,
        "action": activity.action,
        "detail": activity.detail,
        "actor_user_id": activity.actor_user_id,
        "actor_name": _display_name(activity.actor),
        "created_at": activity.created_at,
        "updated_at": activity.updated_at,
    }


def _note_payload(note: CaseNote) -> dict:
    return {
        "id": note.id,
        "body": note.body,
        "author_user_id": note.author_user_id,
        "author_name": _display_name(note.author),
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


def _is_party(case: Case, user: User) -> bool:
    """True when ``user`` is one of the two parties of the case: the client who
    posted it or the lawyer assigned to it. Only parties may see the full
    decision history and activity trail."""
    return user.id in (case.posted_by_user_id, case.assigned_lawyer_id)


def _case_summary(case: Case, user: User) -> dict:
    latest = _my_latest_decision(case, user.id)
    return {
        "id": case.id,
        "title": case.title,
        "category": case.category,
        "summary": case.summary,
        "jurisdiction": case.jurisdiction,
        "urgency": case.urgency,
        "consultation_method": case.consultation_method,
        "budget": case.budget,
        "contact_preference": case.contact_preference,
        "client_reference": case.client_reference,
        "status": case.status,
        "posted_by_user_id": case.posted_by_user_id,
        "posted_by_name": _display_name(case.posted_by),
        "assigned_lawyer_id": case.assigned_lawyer_id,
        "assigned_lawyer_name": _display_name(case.assigned_lawyer),
        "document_count": len(case.documents),
        "decision_count": len(case.decisions),
        "my_decision": latest.decision if latest else None,
        "deadline": case.deadline,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "accepted_at": case.accepted_at,
        "completed_at": case.completed_at,
    }


def _case_detail(case: Case, user: User) -> dict:
    payload = _case_summary(case, user)
    payload["documents"] = [_document_payload(link) for link in case.documents]
    # Privacy: a browsing lawyer on the open marketplace must not see other
    # lawyers' decisions (including rejection reasons and information requests)
    # or the case's activity trail. Only the two parties do. Document metadata
    # stays visible because it is needed to assess the matter.
    if _is_party(case, user):
        payload["decisions"] = [
            _decision_payload(decision)
            for decision in sorted(
                case.decisions,
                key=lambda decision: (decision.created_at, decision.id),
                reverse=True,
            )
        ]
        payload["activities"] = [
            _activity_payload(activity)
            for activity in sorted(
                case.activities,
                key=lambda activity: (activity.created_at, activity.id),
                reverse=True,
            )
        ]
    else:
        payload["decisions"] = []
        payload["activities"] = []
    if case.assigned_lawyer_id == user.id:
        payload["notes"] = [
            _note_payload(note)
            for note in sorted(case.notes, key=lambda note: (note.created_at, note.id), reverse=True)
        ]
    else:
        payload["notes"] = []
    return payload


def _ensure_viewable(case: Case, user: User) -> None:
    """Raise 404 unless the user may see the case.

    Allowed: the client who posted it, the assigned lawyer, or any lawyer while
    the case is still OPEN (the available-cases marketplace).
    """

    if user.id in (case.posted_by_user_id, case.assigned_lawyer_id):
        return
    if user.role == "lawyer" and case.status == "OPEN":
        return
    raise NotFoundError(
        f"Case {case.id} was not found.",
        code="case_not_found",
        details={"case_id": case.id},
    )


def _ensure_available(case: Case, user: User) -> None:
    if case.posted_by_user_id == user.id:
        raise ForbiddenError(
            "You cannot act on a case you posted.", code="own_case"
        )
    if case.status != "OPEN" or case.assigned_lawyer_id is not None:
        raise ConflictError(
            "This case has already been taken by another lawyer.",
            code="case_already_assigned",
        )


def _sort_cases(cases: list[Case], sort: str) -> list[Case]:
    if sort == "urgency":
        return sorted(
            cases,
            key=lambda case: (
                URGENCY_RANK.get(case.urgency, 99),
                -case.created_at.timestamp(),
            ),
        )
    if sort == "oldest":
        return sorted(cases, key=lambda case: (case.created_at, case.id))
    # default: most recent first
    return sorted(cases, key=lambda case: (case.created_at, case.id), reverse=True)


@router.post("/cases", response_model=CaseDetail, status_code=201)
def create_case(db: DbSession, user: CurrentUser, payload: CaseCreate) -> dict:
    case = Case(
        posted_by_user_id=user.id,
        title=payload.title.strip(),
        category=payload.category,
        summary=payload.summary.strip(),
        jurisdiction=payload.jurisdiction,
        urgency=payload.urgency,
        consultation_method=payload.consultation_method,
        budget=payload.budget,
        contact_preference=payload.contact_preference,
        client_reference=payload.client_reference,
        deadline=payload.deadline,
        status="OPEN",
    )
    db.add(case)
    db.flush()

    if payload.document_ids:
        document_ids = list(dict.fromkeys(payload.document_ids))
        documents = db.scalars(
            select(Document).where(
                Document.id.in_(document_ids), Document.user_id == user.id
            )
        ).all()
        found = {document.id for document in documents}
        missing = sorted(set(document_ids) - found)
        if missing:
            db.rollback()
            raise ValidationFailed(
                "Some documents do not exist or do not belong to you.",
                code="invalid_documents",
                details={"document_ids": missing},
            )
        for document in documents:
            db.add(
                CaseDocument(
                    case_id=case.id,
                    document_id=document.id,
                    shared_by_user_id=user.id,
                )
            )

    db.add(
        CaseActivity(
            case_id=case.id,
            actor_user_id=user.id,
            action="CREATED",
            detail=f"{_display_name(user)} posted the case.",
        )
    )
    db.commit()

    loaded = _load_case(db, case.id)
    assert loaded is not None
    return _case_detail(loaded, user)


@router.get("/cases/overview", response_model=LawyerOverview)
def lawyer_overview(db: DbSession, user: LawyerUser) -> dict:
    decided = _decided_case_ids(user.id)
    available_filter = and_(
        Case.status == "OPEN",
        Case.posted_by_user_id != user.id,
        Case.id.notin_(decided),
    )

    available_cases = db.scalar(
        select(func.count()).select_from(Case).where(available_filter)
    )
    active_cases = db.scalar(
        select(func.count())
        .select_from(Case)
        .where(Case.assigned_lawyer_id == user.id, Case.status.in_(ACTIVE_STATUSES))
    )
    completed_cases = db.scalar(
        select(func.count())
        .select_from(Case)
        .where(Case.assigned_lawyer_id == user.id, Case.status.in_(COMPLETED_STATUSES))
    )
    pending_requests = db.scalar(
        select(func.count(func.distinct(CaseDecision.case_id)))
        .select_from(CaseDecision)
        .join(Case, Case.id == CaseDecision.case_id)
        .where(
            CaseDecision.lawyer_id == user.id,
            CaseDecision.decision == "REQUEST_INFO",
            Case.status == "OPEN",
            or_(Case.assigned_lawyer_id.is_(None), Case.assigned_lawyer_id != user.id),
        )
    )
    unread = db.scalar(
        select(func.count())
        .select_from(CaseMessage)
        .join(Case, Case.id == CaseMessage.case_id)
        .where(
            Case.assigned_lawyer_id == user.id,
            CaseMessage.sender_user_id != user.id,
            CaseMessage.read_at.is_(None),
        )
    )
    # Replies the client has sent in this lawyer's pre-assignment clarification
    # threads on cases still open.
    unread_clarifications = db.scalar(
        select(func.count())
        .select_from(CaseClarificationMessage)
        .where(
            CaseClarificationMessage.lawyer_id == user.id,
            CaseClarificationMessage.sender_user_id != user.id,
            CaseClarificationMessage.read_at.is_(None),
        )
    )

    status_rows = db.execute(
        select(Case.status, func.count())
        .where(Case.assigned_lawyer_id == user.id)
        .group_by(Case.status)
    ).all()
    status_distribution = {"ASSIGNED": 0, "COMPLETED": 0, "CLOSED": 0}
    for status, count in status_rows:
        status_distribution[status] = count

    category_rows = db.execute(
        select(Case.category, func.count())
        .where(
            or_(
                Case.assigned_lawyer_id == user.id,
                available_filter,
            )
        )
        .group_by(Case.category)
    ).all()
    category_distribution = [
        {"category": category or "other", "count": count}
        for category, count in sorted(
            category_rows, key=lambda row: row[1], reverse=True
        )
    ]

    return {
        "available_cases": available_cases or 0,
        "pending_requests": pending_requests or 0,
        "active_cases": active_cases or 0,
        "completed_cases": completed_cases or 0,
        # Every case this lawyer has taken on: active plus completed/closed.
        "total_handled": (active_cases or 0) + (completed_cases or 0),
        # Messages sent by the client that this lawyer has not read yet: both
        # assigned-case workspace messages and pre-assignment clarification
        # replies.
        "unread_messages": (unread or 0) + (unread_clarifications or 0),
        "case_status_distribution": status_distribution,
        "case_category_distribution": category_distribution,
    }


@router.get("/cases/mine", response_model=MyCasesResponse)
def my_cases(db: DbSession, user: LawyerUser) -> dict:
    assigned = list(
        db.scalars(
            _case_query().where(Case.assigned_lawyer_id == user.id)
        ).all()
    )
    assigned_by_id = {case.id: case for case in assigned}

    decided_ids = list(db.scalars(_decided_case_ids(user.id)).all())
    others: list[Case] = []
    if decided_ids:
        others = list(
            db.scalars(
                _case_query().where(
                    Case.id.in_(decided_ids),
                    or_(
                        Case.assigned_lawyer_id.is_(None),
                        Case.assigned_lawyer_id != user.id,
                    ),
                )
            ).all()
        )

    active: list[dict] = []
    completed: list[dict] = []
    pending: list[dict] = []
    declined: list[dict] = []

    for case in assigned:
        summary = _case_summary(case, user)
        if case.status in ACTIVE_STATUSES:
            active.append(summary)
        else:
            completed.append(summary)

    for case in others:
        latest = _my_latest_decision(case, user.id)
        summary = _case_summary(case, user)
        if latest is not None and latest.decision == "REQUEST_INFO":
            pending.append(summary)
        elif latest is not None and latest.decision == "REJECT":
            declined.append(summary)

    active.sort(key=lambda item: (item["accepted_at"] or item["created_at"]), reverse=True)
    completed.sort(key=lambda item: (item["completed_at"] or item["updated_at"]), reverse=True)
    pending.sort(key=lambda item: item["updated_at"], reverse=True)
    declined.sort(key=lambda item: item["updated_at"], reverse=True)

    return {
        "active": active,
        "completed": completed,
        "pending": pending,
        "declined": declined,
    }


@router.get("/cases", response_model=CaseListResponse)
def list_cases(
    db: DbSession,
    user: CurrentUser,
    q: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=32),
    urgency: str | None = Query(default=None, max_length=16),
    sort: str = Query(default="recent", pattern="^(recent|oldest|urgency)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    stmt = _case_query()

    if user.role == "lawyer":
        # Available marketplace: open cases the lawyer has not already acted on
        # and did not post themselves.
        stmt = stmt.where(
            Case.status == "OPEN",
            Case.posted_by_user_id != user.id,
            Case.id.notin_(_decided_case_ids(user.id)),
        )
    else:
        stmt = stmt.where(Case.posted_by_user_id == user.id)

    if q and q.strip():
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Case.title).like(pattern),
                func.lower(Case.summary).like(pattern),
            )
        )
    if category and category.strip().lower() != "all":
        wanted = category.strip().lower()
        if wanted not in CASE_CATEGORIES:
            raise ValidationFailed(f"Unsupported category: {category}", code="invalid_category")
        stmt = stmt.where(Case.category == wanted)
    if urgency and urgency.strip().upper() != "ALL":
        wanted = urgency.strip().upper()
        if wanted not in CASE_URGENCIES:
            raise ValidationFailed(f"Unsupported urgency: {urgency}", code="invalid_urgency")
        stmt = stmt.where(Case.urgency == wanted)

    cases = _sort_cases(list(db.scalars(stmt).all()), sort)
    summaries = [_case_summary(case, user) for case in cases]
    return {"items": summaries[offset : offset + limit], "total": len(summaries)}


@router.get("/cases/user-overview", response_model=ClientOverview)
def client_overview(db: DbSession, user: CurrentUser) -> dict:
    """Real, client-scoped caseload statistics. Counts come straight from the
    database; nothing is estimated. ``unread_messages`` only counts messages the
    client has genuinely not read on assigned cases."""

    posted = Case.posted_by_user_id == user.id
    submitted = db.scalar(select(func.count()).select_from(Case).where(posted))
    open_requests = db.scalar(
        select(func.count())
        .select_from(Case)
        .where(posted, Case.status == "OPEN", Case.assigned_lawyer_id.is_(None))
    )
    active_matters = db.scalar(
        select(func.count())
        .select_from(Case)
        .where(posted, Case.status.in_(ACTIVE_STATUSES))
    )
    completed_matters = db.scalar(
        select(func.count())
        .select_from(Case)
        .where(posted, Case.status.in_(COMPLETED_STATUSES))
    )

    now = datetime.now(timezone.utc)
    upcoming = db.scalar(
        select(func.count())
        .select_from(CaseAppointment)
        .join(Case, Case.id == CaseAppointment.case_id)
        .where(
            posted,
            CaseAppointment.status == "CONFIRMED",
            CaseAppointment.scheduled_at >= now,
        )
    )

    unread = db.scalar(
        select(func.count())
        .select_from(CaseMessage)
        .join(Case, Case.id == CaseMessage.case_id)
        .where(
            posted,
            CaseMessage.sender_user_id != user.id,
            CaseMessage.read_at.is_(None),
        )
    )
    # Questions lawyers have asked in clarification threads on this client's
    # still-open cases and that the client has not read yet.
    unread_clarifications = db.scalar(
        select(func.count())
        .select_from(CaseClarificationMessage)
        .join(Case, Case.id == CaseClarificationMessage.case_id)
        .where(
            posted,
            CaseClarificationMessage.sender_user_id != user.id,
            CaseClarificationMessage.read_at.is_(None),
        )
    )

    status_rows = db.execute(
        select(Case.status, func.count()).where(posted).group_by(Case.status)
    ).all()
    status_distribution = {"OPEN": 0, "ASSIGNED": 0, "COMPLETED": 0, "CLOSED": 0}
    for status, count in status_rows:
        status_distribution[status] = count

    category_rows = db.execute(
        select(Case.category, func.count()).where(posted).group_by(Case.category)
    ).all()
    category_distribution = [
        {"category": category or "other", "count": count}
        for category, count in sorted(category_rows, key=lambda row: row[1], reverse=True)
    ]

    return {
        "submitted_cases": submitted or 0,
        "open_requests": open_requests or 0,
        "active_matters": active_matters or 0,
        "completed_matters": completed_matters or 0,
        "upcoming_consultations": upcoming or 0,
        "unread_messages": (unread or 0) + (unread_clarifications or 0),
        "case_status_distribution": status_distribution,
        "case_category_distribution": category_distribution,
    }


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(db: DbSession, user: CurrentUser, case_id: int) -> dict:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_viewable(case, user)
    return _case_detail(case, user)


def _record(db: DbSession, *, case_id: int, user: User, action: str, detail: str) -> None:
    db.add(
        CaseActivity(
            case_id=case_id, actor_user_id=user.id, action=action, detail=detail
        )
    )


@router.post("/cases/{case_id}/accept", response_model=CaseDetail)
def accept_case(db: DbSession, user: LawyerUser, case_id: int) -> dict:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_available(case, user)

    if case.assigned_lawyer_id == user.id:
        raise ConflictError(
            "You have already accepted this case.", code="case_already_yours"
        )

    # Invalid transition: a lawyer who declined a case cannot later accept it.
    declined = db.scalar(
        select(CaseDecision.id).where(
            CaseDecision.case_id == case_id,
            CaseDecision.lawyer_id == user.id,
            CaseDecision.decision == "REJECT",
        )
    )
    if declined is not None:
        raise ConflictError(
            "You have already declined this case.", code="already_declined"
        )

    now = datetime.now(timezone.utc)
    # Atomic exclusive assignment: only one conditional UPDATE can match while
    # the case is open and unassigned, so concurrent accepts cannot both win.
    result = db.execute(
        update(Case)
        .where(
            Case.id == case_id,
            Case.status == "OPEN",
            Case.assigned_lawyer_id.is_(None),
        )
        .values(status="ASSIGNED", assigned_lawyer_id=user.id, accepted_at=now)
    )
    if result.rowcount == 0:
        db.rollback()
        raise ConflictError(
            "This case has already been taken by another lawyer.",
            code="case_already_assigned",
        )

    _record(
        db,
        case_id=case_id,
        user=user,
        action="ACCEPTED",
        detail=f"{_display_name(user)} accepted the case.",
    )
    db.add(CaseDecision(case_id=case_id, lawyer_id=user.id, decision="ACCEPT"))
    db.commit()

    loaded = _load_case(db, case_id)
    assert loaded is not None
    return _case_detail(loaded, user)


@router.post("/cases/{case_id}/reject", response_model=CaseDetail)
def reject_case(
    db: DbSession, user: LawyerUser, case_id: int, payload: CaseDecisionCreate
) -> dict:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_available(case, user)

    reason = (payload.reason or "").strip()
    if not reason:
        raise ValidationFailed(
            "A reason is required when declining a case.", code="reason_required"
        )

    existing = db.scalar(
        select(CaseDecision).where(
            CaseDecision.case_id == case_id,
            CaseDecision.lawyer_id == user.id,
            CaseDecision.decision == "REJECT",
        )
    )
    if existing is not None:
        raise ConflictError(
            "You have already declined this case.", code="already_declined"
        )

    db.add(
        CaseDecision(
            case_id=case_id, lawyer_id=user.id, decision="REJECT", reason=reason
        )
    )
    _record(
        db,
        case_id=case_id,
        user=user,
        action="DECLINED",
        detail=f"{_display_name(user)} declined the case.",
    )
    db.commit()

    loaded = _load_case(db, case_id)
    assert loaded is not None
    return _case_detail(loaded, user)


@router.post("/cases/{case_id}/request-info", response_model=CaseDetail)
def request_case_info(
    db: DbSession, user: LawyerUser, case_id: int, payload: CaseDecisionCreate
) -> dict:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_available(case, user)

    message = (payload.message or "").strip()
    if not message:
        raise ValidationFailed(
            "A message is required when requesting more information.",
            code="message_required",
        )

    existing = db.scalar(
        select(CaseDecision).where(
            CaseDecision.case_id == case_id,
            CaseDecision.lawyer_id == user.id,
            CaseDecision.decision == "REQUEST_INFO",
        )
    )
    if existing is not None:
        raise ConflictError(
            "You have already requested more information on this case.",
            code="already_requested",
        )

    db.add(
        CaseDecision(
            case_id=case_id,
            lawyer_id=user.id,
            decision="REQUEST_INFO",
            message=message,
        )
    )
    # Open a private clarification thread so the client can answer while the
    # case is still open, without exposing the exchange to other lawyers.
    db.add(
        CaseClarificationMessage(
            case_id=case_id,
            lawyer_id=user.id,
            sender_user_id=user.id,
            body=message,
        )
    )
    _record(
        db,
        case_id=case_id,
        user=user,
        action="INFO_REQUESTED",
        detail=f"{_display_name(user)} requested more information.",
    )
    db.commit()

    loaded = _load_case(db, case_id)
    assert loaded is not None
    return _case_detail(loaded, user)


@router.post("/cases/{case_id}/complete", response_model=CaseDetail)
def complete_case(db: DbSession, user: LawyerUser, case_id: int) -> dict:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    if case.assigned_lawyer_id != user.id:
        raise ForbiddenError(
            "Only the assigned lawyer can complete this case.", code="not_assigned"
        )
    if case.status != "ASSIGNED":
        raise ConflictError(
            "Only an active case can be completed.", code="case_not_active"
        )

    now = datetime.now(timezone.utc)
    case.status = "COMPLETED"
    case.completed_at = now
    _record(
        db,
        case_id=case_id,
        user=user,
        action="COMPLETED",
        detail=f"{_display_name(user)} marked the case completed.",
    )
    db.commit()

    loaded = _load_case(db, case_id)
    assert loaded is not None
    return _case_detail(loaded, user)


@router.post("/cases/{case_id}/notes", response_model=CaseDetail, status_code=201)
def add_case_note(
    db: DbSession, user: LawyerUser, case_id: int, payload: CaseNoteCreate
) -> dict:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    if case.assigned_lawyer_id != user.id:
        raise ForbiddenError(
            "Only the assigned lawyer can add private notes.", code="not_assigned"
        )

    db.add(CaseNote(case_id=case_id, author_user_id=user.id, body=payload.body.strip()))
    db.commit()

    loaded = _load_case(db, case_id)
    assert loaded is not None
    return _case_detail(loaded, user)


# ---------------------------------------------------------------------------
# Private client / lawyer workspace.
#
# Every endpoint below is scoped to the two parties of an *assigned* case: the
# client who posted it and the lawyer who accepted it. Anyone else (including
# other lawyers) receives 404 so the case's existence is not disclosed.
# ---------------------------------------------------------------------------


def _ensure_case_party(case: Case, user: User) -> None:
    if user.id not in (case.posted_by_user_id, case.assigned_lawyer_id):
        raise NotFoundError(
            f"Case {case.id} was not found.",
            code="case_not_found",
            details={"case_id": case.id},
        )
    if case.assigned_lawyer_id is None:
        raise ConflictError(
            "This case has no assigned lawyer yet.",
            code="case_not_assigned",
        )


def _message_payload(message: CaseMessage) -> dict:
    return {
        "id": message.id,
        "sender_user_id": message.sender_user_id,
        "sender_name": _display_name(message.sender),
        "body": message.body,
        "read_at": message.read_at,
        "created_at": message.created_at,
        "updated_at": message.updated_at,
    }


def _unread_messages(db: DbSession, case_id: int, user_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(CaseMessage)
            .where(
                CaseMessage.case_id == case_id,
                CaseMessage.sender_user_id != user_id,
                CaseMessage.read_at.is_(None),
            )
        )
        or 0
    )


def _messages_payload(db: DbSession, case: Case, user: User) -> dict:
    messages = list(
        db.scalars(
            select(CaseMessage)
            .where(CaseMessage.case_id == case.id)
            .order_by(CaseMessage.created_at, CaseMessage.id)
        ).all()
    )
    return {
        "items": [_message_payload(message) for message in messages],
        "unread": _unread_messages(db, case.id, user.id),
    }


def _fee_payload(proposal: CaseFeeProposal) -> dict:
    return {
        "id": proposal.id,
        "proposed_by_user_id": proposal.proposed_by_user_id,
        "proposed_by_name": _display_name(proposal.proposed_by),
        "amount": proposal.amount,
        "currency": proposal.currency,
        "note": proposal.note,
        "status": proposal.status,
        "created_at": proposal.created_at,
        "updated_at": proposal.updated_at,
    }


def _fees_payload(db: DbSession, case: Case) -> list[dict]:
    proposals = db.scalars(
        select(CaseFeeProposal)
        .where(CaseFeeProposal.case_id == case.id)
        .order_by(CaseFeeProposal.created_at.desc(), CaseFeeProposal.id.desc())
    ).all()
    return [_fee_payload(proposal) for proposal in proposals]


def _appointment_payload(appointment: CaseAppointment) -> dict:
    return {
        "id": appointment.id,
        "proposed_by_user_id": appointment.proposed_by_user_id,
        "proposed_by_name": _display_name(appointment.proposed_by),
        "scheduled_at": appointment.scheduled_at,
        "duration_minutes": appointment.duration_minutes,
        "mode": appointment.mode,
        "location": appointment.location,
        "notes": appointment.notes,
        "status": appointment.status,
        "created_at": appointment.created_at,
        "updated_at": appointment.updated_at,
    }


def _appointments_payload(db: DbSession, case: Case) -> list[dict]:
    appointments = db.scalars(
        select(CaseAppointment)
        .where(CaseAppointment.case_id == case.id)
        .order_by(CaseAppointment.scheduled_at, CaseAppointment.id)
    ).all()
    return [_appointment_payload(appointment) for appointment in appointments]


@router.post("/cases/{case_id}/documents", response_model=CaseDetail, status_code=201)
def share_case_document(
    db: DbSession, user: CurrentUser, case_id: int, payload: CaseDocumentAttach
) -> dict:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    # Only the client who posted the case may share their own documents into it.
    # Anyone else gets 404 so the case's existence is not disclosed.
    if case.posted_by_user_id != user.id:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    if case.status in COMPLETED_STATUSES:
        raise ConflictError("This case is closed.", code="case_closed")

    document = db.scalar(
        select(Document).where(
            Document.id == payload.document_id, Document.user_id == user.id
        )
    )
    if document is None:
        raise ValidationFailed(
            "That document does not exist or does not belong to you.",
            code="invalid_documents",
            details={"document_ids": [payload.document_id]},
        )

    existing = db.scalar(
        select(CaseDocument).where(
            CaseDocument.case_id == case.id,
            CaseDocument.document_id == document.id,
        )
    )
    if existing is not None:
        raise ConflictError(
            "That document is already attached to this case.",
            code="document_already_attached",
        )

    db.add(
        CaseDocument(
            case_id=case.id, document_id=document.id, shared_by_user_id=user.id
        )
    )
    _record(
        db,
        case_id=case.id,
        user=user,
        action="DOCUMENT_SHARED",
        detail=f"{_display_name(user)} shared a document.",
    )
    db.commit()

    loaded = _load_case(db, case_id)
    assert loaded is not None
    return _case_detail(loaded, user)


@router.get("/cases/{case_id}/messages", response_model=CaseMessageListResponse)
def list_case_messages(db: DbSession, user: CurrentUser, case_id: int) -> dict:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_case_party(case, user)
    return _messages_payload(db, case, user)


@router.post(
    "/cases/{case_id}/messages",
    response_model=CaseMessageListResponse,
    status_code=201,
)
def send_case_message(
    db: DbSession, user: CurrentUser, case_id: int, payload: CaseMessageCreate
) -> dict:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_case_party(case, user)

    db.add(
        CaseMessage(case_id=case.id, sender_user_id=user.id, body=payload.body.strip())
    )
    db.commit()
    return _messages_payload(db, case, user)


@router.post("/cases/{case_id}/messages/read", response_model=CaseMessageListResponse)
def mark_case_messages_read(db: DbSession, user: CurrentUser, case_id: int) -> dict:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_case_party(case, user)

    db.execute(
        update(CaseMessage)
        .where(
            CaseMessage.case_id == case.id,
            CaseMessage.sender_user_id != user.id,
            CaseMessage.read_at.is_(None),
        )
        .values(read_at=datetime.now(timezone.utc))
    )
    db.commit()
    return _messages_payload(db, case, user)


# ---------------------------------------------------------------------------
# Pre-assignment clarifications.
#
# While a case is OPEN and unassigned an interested lawyer may ask the client
# for more information, and the client may answer. Each conversation is a
# private thread keyed by (case_id, lawyer_id): only that lawyer and the client
# can read or write it, so competing lawyers never see one another's questions
# or the client's answers. This is separate from the assigned-case workspace.
# ---------------------------------------------------------------------------


def _clarification_payload(message: CaseClarificationMessage) -> dict:
    return {
        "id": message.id,
        "lawyer_id": message.lawyer_id,
        "sender_user_id": message.sender_user_id,
        "sender_name": _display_name(message.sender),
        "body": message.body,
        "read_at": message.read_at,
        "created_at": message.created_at,
        "updated_at": message.updated_at,
    }


def _clarifications_payload(db: DbSession, case: Case, user: User) -> dict:
    """Return the clarification threads visible to ``user``.

    The client who posted the case sees every thread. A lawyer sees only their
    own thread. Anyone else (who can still view the open case) sees nothing.
    """

    if user.id == case.posted_by_user_id:
        rows = list(
            db.scalars(
                select(CaseClarificationMessage)
                .where(CaseClarificationMessage.case_id == case.id)
                .order_by(CaseClarificationMessage.created_at, CaseClarificationMessage.id)
            ).all()
        )
        grouped: dict[int, list[CaseClarificationMessage]] = {}
        for row in rows:
            grouped.setdefault(row.lawyer_id, []).append(row)
        threads = []
        for lawyer_id in sorted(grouped):
            items = grouped[lawyer_id]
            unread = sum(
                1
                for item in items
                if item.sender_user_id != user.id and item.read_at is None
            )
            threads.append(
                {
                    "lawyer_id": lawyer_id,
                    "lawyer_name": _display_name(items[0].lawyer),
                    "unread": unread,
                    "items": [_clarification_payload(item) for item in items],
                }
            )
        return {"threads": threads}

    if user.role == "lawyer":
        rows = list(
            db.scalars(
                select(CaseClarificationMessage)
                .where(
                    CaseClarificationMessage.case_id == case.id,
                    CaseClarificationMessage.lawyer_id == user.id,
                )
                .order_by(CaseClarificationMessage.created_at, CaseClarificationMessage.id)
            ).all()
        )
        if not rows:
            return {"threads": []}
        unread = sum(
            1 for item in rows if item.sender_user_id != user.id and item.read_at is None
        )
        return {
            "threads": [
                {
                    "lawyer_id": user.id,
                    "lawyer_name": _display_name(user),
                    "unread": unread,
                    "items": [_clarification_payload(item) for item in rows],
                }
            ]
        }

    return {"threads": []}


@router.get(
    "/cases/{case_id}/clarifications",
    response_model=CaseClarificationThreadsResponse,
)
def list_case_clarifications(db: DbSession, user: CurrentUser, case_id: int) -> dict:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_viewable(case, user)
    return _clarifications_payload(db, case, user)


@router.post(
    "/cases/{case_id}/clarifications",
    response_model=CaseClarificationThreadsResponse,
    status_code=201,
)
def create_case_clarification(
    db: DbSession, user: CurrentUser, case_id: int, payload: CaseClarificationCreate
) -> dict:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_viewable(case, user)
    if case.status in COMPLETED_STATUSES:
        raise ConflictError("This case is closed.", code="case_closed")

    message = payload.message.strip()
    if not message:
        raise ValidationFailed("A message is required.", code="message_required")

    # The client who posted the case answers a specific lawyer's thread.
    if user.id == case.posted_by_user_id:
        if case.assigned_lawyer_id is not None:
            raise ConflictError(
                "This case is already assigned; continue in the case workspace.",
                code="case_already_assigned",
            )
        if payload.lawyer_id is None:
            raise ValidationFailed(
                "A lawyer must be specified when replying.", code="lawyer_id_required"
            )
        thread_exists = db.scalar(
            select(CaseClarificationMessage.id)
            .where(
                CaseClarificationMessage.case_id == case.id,
                CaseClarificationMessage.lawyer_id == payload.lawyer_id,
            )
            .limit(1)
        )
        if thread_exists is None:
            raise NotFoundError(
                "There is no open information request from that lawyer.",
                code="clarification_not_found",
                details={"lawyer_id": payload.lawyer_id},
            )
        db.add(
            CaseClarificationMessage(
                case_id=case.id,
                lawyer_id=payload.lawyer_id,
                sender_user_id=user.id,
                body=message,
            )
        )
        db.commit()
        loaded = _load_case(db, case.id)
        assert loaded is not None
        return _clarifications_payload(db, loaded, user)

    # An interested lawyer asks or follows up on their own thread only.
    if user.role == "lawyer":
        if case.assigned_lawyer_id is not None:
            raise ConflictError(
                "This case is already assigned; continue in the case workspace.",
                code="case_already_assigned",
            )
        decision = db.scalar(
            select(CaseDecision).where(
                CaseDecision.case_id == case.id,
                CaseDecision.lawyer_id == user.id,
                CaseDecision.decision == "REQUEST_INFO",
            )
        )
        if decision is None:
            db.add(
                CaseDecision(
                    case_id=case.id,
                    lawyer_id=user.id,
                    decision="REQUEST_INFO",
                    message=message,
                )
            )
            _record(
                db,
                case_id=case.id,
                user=user,
                action="INFO_REQUESTED",
                detail=f"{_display_name(user)} requested more information.",
            )
        db.add(
            CaseClarificationMessage(
                case_id=case.id,
                lawyer_id=user.id,
                sender_user_id=user.id,
                body=message,
            )
        )
        db.commit()
        loaded = _load_case(db, case.id)
        assert loaded is not None
        return _clarifications_payload(db, loaded, user)

    raise ForbiddenError("You cannot post to this case.", code="not_a_party")


@router.post(
    "/cases/{case_id}/clarifications/read",
    response_model=CaseClarificationThreadsResponse,
)
def mark_case_clarifications_read(
    db: DbSession,
    user: CurrentUser,
    case_id: int,
    payload: CaseClarificationReadMark | None = None,
) -> dict:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_viewable(case, user)

    stmt = update(CaseClarificationMessage).where(
        CaseClarificationMessage.case_id == case.id,
        CaseClarificationMessage.sender_user_id != user.id,
        CaseClarificationMessage.read_at.is_(None),
    )
    if user.id == case.posted_by_user_id:
        if payload is not None and payload.lawyer_id is not None:
            stmt = stmt.where(CaseClarificationMessage.lawyer_id == payload.lawyer_id)
    elif user.role == "lawyer":
        stmt = stmt.where(CaseClarificationMessage.lawyer_id == user.id)
    else:
        raise ForbiddenError("You cannot access this case.", code="not_a_party")

    db.execute(stmt.values(read_at=datetime.now(timezone.utc)))
    db.commit()
    loaded = _load_case(db, case.id)
    assert loaded is not None
    return _clarifications_payload(db, loaded, user)


@router.get("/cases/{case_id}/fees", response_model=list[CaseFeeProposalRead])
def list_case_fees(db: DbSession, user: CurrentUser, case_id: int) -> list[dict]:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_case_party(case, user)
    return _fees_payload(db, case)


@router.post(
    "/cases/{case_id}/fees",
    response_model=list[CaseFeeProposalRead],
    status_code=201,
)
def propose_case_fee(
    db: DbSession, user: CurrentUser, case_id: int, payload: CaseFeeProposalCreate
) -> list[dict]:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_case_party(case, user)

    # A new proposal supersedes any still-open one.
    db.execute(
        update(CaseFeeProposal)
        .where(
            CaseFeeProposal.case_id == case.id,
            CaseFeeProposal.status == "PROPOSED",
        )
        .values(status="SUPERSEDED")
    )
    db.add(
        CaseFeeProposal(
            case_id=case.id,
            proposed_by_user_id=user.id,
            amount=payload.amount.strip(),
            currency=(payload.currency or "INR").strip().upper(),
            note=(payload.note or "").strip() or None,
            status="PROPOSED",
        )
    )
    _record(
        db,
        case_id=case.id,
        user=user,
        action="FEE_PROPOSED",
        detail=f"{_display_name(user)} proposed a fee.",
    )
    db.commit()
    return _fees_payload(db, case)


def _get_fee_or_404(db: DbSession, case_id: int, proposal_id: int) -> CaseFeeProposal:
    proposal = db.scalar(
        select(CaseFeeProposal).where(
            CaseFeeProposal.id == proposal_id, CaseFeeProposal.case_id == case_id
        )
    )
    if proposal is None:
        raise NotFoundError(
            f"Fee proposal {proposal_id} was not found.",
            code="fee_proposal_not_found",
            details={"proposal_id": proposal_id},
        )
    return proposal


@router.post(
    "/cases/{case_id}/fees/{proposal_id}/accept",
    response_model=list[CaseFeeProposalRead],
)
def accept_case_fee(
    db: DbSession, user: CurrentUser, case_id: int, proposal_id: int
) -> list[dict]:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_case_party(case, user)
    proposal = _get_fee_or_404(db, case.id, proposal_id)
    if proposal.status != "PROPOSED":
        raise ConflictError(
            "This fee proposal is no longer open.", code="proposal_not_open"
        )
    # Only the other party may accept. The proposer withdraws a proposal by
    # making a new one (which supersedes the open proposal).
    if proposal.proposed_by_user_id == user.id:
        raise ForbiddenError(
            "You cannot accept your own fee proposal.", code="own_proposal"
        )

    db.execute(
        update(CaseFeeProposal)
        .where(
            CaseFeeProposal.case_id == case.id,
            CaseFeeProposal.status == "PROPOSED",
            CaseFeeProposal.id != proposal.id,
        )
        .values(status="SUPERSEDED")
    )
    proposal.status = "ACCEPTED"
    _record(
        db,
        case_id=case.id,
        user=user,
        action="FEE_ACCEPTED",
        detail=f"{_display_name(user)} accepted the proposed fee.",
    )
    db.commit()
    return _fees_payload(db, case)


@router.post(
    "/cases/{case_id}/fees/{proposal_id}/decline",
    response_model=list[CaseFeeProposalRead],
)
def decline_case_fee(
    db: DbSession, user: CurrentUser, case_id: int, proposal_id: int
) -> list[dict]:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_case_party(case, user)
    proposal = _get_fee_or_404(db, case.id, proposal_id)
    if proposal.status != "PROPOSED":
        raise ConflictError(
            "This fee proposal is no longer open.", code="proposal_not_open"
        )
    # Only the other party may decline; the proposer supersedes with a new offer.
    if proposal.proposed_by_user_id == user.id:
        raise ForbiddenError(
            "You cannot decline your own fee proposal.", code="own_proposal"
        )
    proposal.status = "DECLINED"
    _record(
        db,
        case_id=case.id,
        user=user,
        action="FEE_DECLINED",
        detail=f"{_display_name(user)} declined the proposed fee.",
    )
    db.commit()
    return _fees_payload(db, case)


@router.get("/cases/{case_id}/appointments", response_model=list[CaseAppointmentRead])
def list_case_appointments(db: DbSession, user: CurrentUser, case_id: int) -> list[dict]:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_case_party(case, user)
    return _appointments_payload(db, case)


@router.post(
    "/cases/{case_id}/appointments",
    response_model=list[CaseAppointmentRead],
    status_code=201,
)
def propose_case_appointment(
    db: DbSession, user: CurrentUser, case_id: int, payload: CaseAppointmentCreate
) -> list[dict]:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_case_party(case, user)

    db.add(
        CaseAppointment(
            case_id=case.id,
            proposed_by_user_id=user.id,
            scheduled_at=payload.scheduled_at,
            duration_minutes=payload.duration_minutes,
            mode=payload.mode,
            location=payload.location,
            notes=(payload.notes or "").strip() or None,
            status="PROPOSED",
        )
    )
    _record(
        db,
        case_id=case.id,
        user=user,
        action="APPOINTMENT_PROPOSED",
        detail=f"{_display_name(user)} proposed a consultation.",
    )
    db.commit()
    return _appointments_payload(db, case)


def _get_appointment_or_404(
    db: DbSession, case_id: int, appointment_id: int
) -> CaseAppointment:
    appointment = db.scalar(
        select(CaseAppointment).where(
            CaseAppointment.id == appointment_id,
            CaseAppointment.case_id == case_id,
        )
    )
    if appointment is None:
        raise NotFoundError(
            f"Appointment {appointment_id} was not found.",
            code="appointment_not_found",
            details={"appointment_id": appointment_id},
        )
    return appointment


def _set_appointment_status(
    db: DbSession,
    user: User,
    case_id: int,
    appointment_id: int,
    status: str,
    *,
    by_other_party: bool = False,
    required_status: str | None = None,
) -> list[dict]:
    case = _load_case(db, case_id)
    if case is None:
        raise NotFoundError(
            f"Case {case_id} was not found.",
            code="case_not_found",
            details={"case_id": case_id},
        )
    _ensure_case_party(case, user)
    appointment = _get_appointment_or_404(db, case.id, appointment_id)
    if appointment.status == "CANCELLED":
        raise ConflictError(
            "This consultation was already cancelled.", code="appointment_cancelled"
        )
    # Invalid transition: e.g. a consultation that is already CONFIRMED cannot be
    # confirmed again.
    if required_status is not None and appointment.status != required_status:
        raise ConflictError(
            "This consultation is not awaiting confirmation.",
            code="appointment_not_proposed",
        )
    # A party cannot confirm a consultation they proposed themselves; the other
    # party must agree to it.
    if by_other_party and appointment.proposed_by_user_id == user.id:
        raise ForbiddenError(
            "You cannot confirm a consultation you proposed.", code="own_proposal"
        )
    appointment.status = status
    action = "APPOINTMENT_CONFIRMED" if status == "CONFIRMED" else "APPOINTMENT_CANCELLED"
    detail = (
        f"{_display_name(user)} confirmed the consultation."
        if status == "CONFIRMED"
        else f"{_display_name(user)} cancelled the consultation."
    )
    _record(db, case_id=case.id, user=user, action=action, detail=detail)
    db.commit()
    return _appointments_payload(db, case)


@router.post(
    "/cases/{case_id}/appointments/{appointment_id}/confirm",
    response_model=list[CaseAppointmentRead],
)
def confirm_case_appointment(
    db: DbSession, user: CurrentUser, case_id: int, appointment_id: int
) -> list[dict]:
    return _set_appointment_status(
        db,
        user,
        case_id,
        appointment_id,
        "CONFIRMED",
        by_other_party=True,
        required_status="PROPOSED",
    )


@router.post(
    "/cases/{case_id}/appointments/{appointment_id}/cancel",
    response_model=list[CaseAppointmentRead],
)
def cancel_case_appointment(
    db: DbSession, user: CurrentUser, case_id: int, appointment_id: int
) -> list[dict]:
    return _set_appointment_status(db, user, case_id, appointment_id, "CANCELLED")


_NOTIFICATION_TITLES = {
    "CREATED": "Case posted",
    "ACCEPTED": "Lawyer assigned to your case",
    "DECLINED": "A lawyer declined a case",
    "INFO_REQUESTED": "Information requested on a case",
    "COMPLETED": "Case marked completed",
    "DOCUMENT_SHARED": "A document was shared",
    "FEE_PROPOSED": "A fee was proposed",
    "FEE_ACCEPTED": "A fee was agreed",
    "FEE_DECLINED": "A fee proposal was declined",
    "APPOINTMENT_PROPOSED": "A consultation was proposed",
    "APPOINTMENT_CONFIRMED": "A consultation was confirmed",
    "APPOINTMENT_CANCELLED": "A consultation was cancelled",
}


@router.get("/notifications", response_model=list[NotificationRead])
def list_notifications(db: DbSession, user: CurrentUser) -> list[dict]:
    """Derived, non-persistent feed of activity on the user's own cases plus any
    messages they have not read. There is no push delivery; this is a read view
    computed from real records on each request."""

    participated = select(Case.id).where(
        or_(
            Case.posted_by_user_id == user.id,
            Case.assigned_lawyer_id == user.id,
        )
    )

    items: list[dict] = []
    activities = db.scalars(
        select(CaseActivity)
        .where(
            CaseActivity.case_id.in_(participated),
            or_(
                CaseActivity.actor_user_id.is_(None),
                CaseActivity.actor_user_id != user.id,
            ),
        )
        .order_by(CaseActivity.created_at.desc(), CaseActivity.id.desc())
        .limit(30)
    ).all()
    for activity in activities:
        items.append(
            {
                "id": f"activity-{activity.id}",
                "kind": activity.action,
                "title": _NOTIFICATION_TITLES.get(activity.action, activity.action.title()),
                "detail": activity.detail,
                "case_id": activity.case_id,
                "created_at": activity.created_at,
            }
        )

    messages = db.scalars(
        select(CaseMessage)
        .where(
            CaseMessage.case_id.in_(participated),
            CaseMessage.sender_user_id != user.id,
            CaseMessage.read_at.is_(None),
        )
        .order_by(CaseMessage.created_at.desc())
        .limit(20)
    ).all()
    for message in messages:
        items.append(
            {
                "id": f"message-{message.id}",
                "kind": "MESSAGE",
                "title": "Unread message",
                "detail": message.body[:140],
                "case_id": message.case_id,
                "created_at": message.created_at,
            }
        )

    # Unread pre-assignment clarification messages addressed to this user: as the
    # lawyer who asked, or as the client who was asked.
    clarifications = db.scalars(
        select(CaseClarificationMessage)
        .where(
            CaseClarificationMessage.sender_user_id != user.id,
            CaseClarificationMessage.read_at.is_(None),
            or_(
                CaseClarificationMessage.lawyer_id == user.id,
                CaseClarificationMessage.case_id.in_(
                    select(Case.id).where(Case.posted_by_user_id == user.id)
                ),
            ),
        )
        .order_by(CaseClarificationMessage.created_at.desc())
        .limit(20)
    ).all()
    for clarification in clarifications:
        items.append(
            {
                "id": f"clarification-{clarification.id}",
                "kind": "MESSAGE",
                "title": "New clarification message",
                "detail": clarification.body[:140],
                "case_id": clarification.case_id,
                "created_at": clarification.created_at,
            }
        )

    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items[:40]


__all__ = ["router"]
