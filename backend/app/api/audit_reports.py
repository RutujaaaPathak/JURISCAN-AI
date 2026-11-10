"""Company audit-report endpoints.

Audit reports are derived from the latest analysis of documents owned by the
authenticated user's company. There is no separate report table and no
fabricated metrics: every value comes from persisted document, analysis, clause
and finding rows. Access is scoped to the session user's company on the server.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Query
from fastapi.responses import Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CompanyUser, DbSession
from app.core.exceptions import NotFoundError, ValidationFailed
from app.models import Analysis, Clause, Document, User
from app.schemas.company import (
    AuditActivity,
    AuditReportDetail,
    AuditReportListResponse,
    AuditReportOverview,
    AuditReportSummary,
)
from app.services.audit import detail_payload, latest_analysis, summary_payload
from app.services.report import build_report_pdf

router = APIRouter(prefix="/company/audit-reports", tags=["company-audit-reports"])

REPORT_STATUSES = ("READY", "PENDING", "FAILED", "NOT_GENERATED")
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def _document_query():
    return select(Document).options(
        selectinload(Document.clauses),
        selectinload(Document.analyses).selectinload(Analysis.risk_findings),
    )


def _company_user_ids(db: DbSession, company_id: int) -> list[int]:
    return list(db.scalars(select(User.id).where(User.company_id == company_id)).all())


def _company_scope_filter(db: DbSession, company_id: int):
    member_ids = _company_user_ids(db, company_id)
    if member_ids:
        return or_(
            Document.company_id == company_id,
            and_(Document.company_id.is_(None), Document.user_id.in_(member_ids)),
        )
    return Document.company_id == company_id


def _company_documents(db: DbSession, company_id: int) -> list[Document]:
    docs = list(
        db.scalars(
            _document_query()
            .where(_company_scope_filter(db, company_id))
            .order_by(Document.updated_at.desc(), Document.id.desc())
        ).all()
    )
    # Automatically backfill company_id for any eligible existing documents
    need_commit = False
    for doc in docs:
        if doc.company_id is None:
            doc.company_id = company_id
            need_commit = True
    if need_commit:
        db.commit()
    return docs


def _get_company_document(
    db: DbSession, company_id: int, document_id: int
) -> Document:
    document = db.scalar(
        _document_query().where(
            Document.id == document_id,
            _company_scope_filter(db, company_id),
        )
    )
    if document is None:
        # 404 (not 403) avoids disclosing whether a document exists in another
        # company.
        raise NotFoundError(
            f"Audit report {document_id} was not found.",
            code="audit_report_not_found",
            details={"document_id": document_id},
        )
    if document.company_id is None:
        document.company_id = company_id
        db.commit()
    return document


def _date_value(value: datetime | None) -> date | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.date()


@router.get("", response_model=AuditReportListResponse)
def list_audit_reports(
    db: DbSession,
    user: CompanyUser,
    q: str | None = Query(default=None, max_length=200),
    risk_level: str | None = Query(default=None, max_length=16),
    report_status: str | None = Query(default=None, max_length=16),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    assert user.company_id is not None

    stmt = _document_query().where(_company_scope_filter(db, user.company_id))
    if q and q.strip():
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Document.title).like(pattern),
                func.lower(Document.filename).like(pattern),
            )
        )
    stmt = stmt.order_by(Document.updated_at.desc(), Document.id.desc())
    documents = list(db.scalars(stmt).all())
    need_commit = False
    for doc in documents:
        if doc.company_id is None:
            doc.company_id = user.company_id
            need_commit = True
    if need_commit:
        db.commit()

    summaries = [summary_payload(document) for document in documents]
    if risk_level:
        wanted = risk_level.upper()
        summaries = [item for item in summaries if item["risk_level"] == wanted]
    if report_status:
        wanted_status = report_status.upper()
        if wanted_status in ("COMPLETED", "READY"):
            summaries = [item for item in summaries if item["report_status"] in ("READY", "COMPLETED")]
        elif wanted_status in ("PROCESSING", "PENDING"):
            summaries = [item for item in summaries if item["report_status"] in ("PENDING", "PROCESSING")]
        elif wanted_status in ("UPLOADED", "NOT_GENERATED"):
            summaries = [item for item in summaries if item["report_status"] in ("NOT_GENERATED", "UPLOADED")]
        elif wanted_status == "FAILED":
            summaries = [item for item in summaries if item["report_status"] == "FAILED"]
        else:
            summaries = [
                item for item in summaries if item["report_status"] == wanted_status
            ]
    if date_from:
        summaries = [
            item
            for item in summaries
            if _date_value(item["audit_date"]) is not None
            and _date_value(item["audit_date"]) >= date_from
        ]
    if date_to:
        summaries = [
            item
            for item in summaries
            if _date_value(item["audit_date"]) is not None
            and _date_value(item["audit_date"]) <= date_to
        ]

    summaries.sort(
        key=lambda item: (
            item["audit_date"] is not None,
            item["audit_date"] or datetime.min.replace(tzinfo=timezone.utc),
            item["document_id"],
        ),
        reverse=True,
    )
    total = len(summaries)
    return {"items": summaries[offset : offset + limit], "total": total}


@router.get("/overview", response_model=AuditReportOverview)
def audit_overview(db: DbSession, user: CompanyUser) -> dict:
    assert user.company_id is not None
    documents = _company_documents(db, user.company_id)
    summaries = [summary_payload(document) for document in documents]

    ready = [item for item in summaries if item["report_status"] == "READY"]
    failed = [item for item in summaries if item["report_status"] == "FAILED"]
    high_risk = [
        item
        for item in ready
        if item["risk_level"] in ("HIGH", "CRITICAL")
    ]
    medium_risk = [
        item
        for item in ready
        if item["risk_level"] == "MEDIUM"
    ]
    low_risk = [
        item
        for item in ready
        if item["risk_level"] == "LOW"
    ]
    scored = [item["risk_score"] for item in ready if item["risk_score"] is not None]
    avg_risk = round(sum(scored) / len(scored), 1) if scored else 0.0

    activity: list[AuditActivity] = []
    for item, document in zip(summaries, documents, strict=False):
        analysis = latest_analysis(document)
        occurred_at = item["audit_date"] or document.updated_at
        if analysis is None:
            event = (
                "Analysis failed"
                if item["report_status"] == "FAILED"
                else "Document uploaded"
            )
        elif analysis.status == "COMPLETED":
            event = "Analysis completed"
        elif analysis.status == "FAILED":
            event = "Analysis failed"
        else:
            event = "Analysis pending"
        activity.append(
            AuditActivity(
                document_id=item["document_id"],
                document_title=item["document_title"],
                event=event,
                report_status=item["report_status"],
                risk_level=item["risk_level"],
                risk_score=item["risk_score"],
                occurred_at=occurred_at,
            )
        )
    activity.sort(key=lambda item: item.occurred_at, reverse=True)

    return {
        "total_reports": len(summaries),
        "ready_reports": len(ready),
        "failed_reports": len(failed),
        "high_risk_reports": len(high_risk),
        "medium_risk_reports": len(medium_risk),
        "low_risk_reports": len(low_risk),
        "requiring_attention": len(
            {item["document_id"] for item in high_risk + failed}
        ),
        "avg_risk_score": avg_risk,
        "recent_activity": activity[:8],
    }


@router.get("/{document_id}", response_model=AuditReportDetail)
def get_audit_report(
    db: DbSession, user: CompanyUser, document_id: int
) -> dict:
    assert user.company_id is not None
    document = _get_company_document(db, user.company_id, document_id)
    return detail_payload(document)


@router.get("/{document_id}/report")
def download_audit_report(
    db: DbSession, user: CompanyUser, document_id: int
) -> Response:
    assert user.company_id is not None
    document = _get_company_document(db, user.company_id, document_id)
    if document.status != "PROCESSED":
        raise ValidationFailed(
            "The report is only available once the document has been analyzed.",
            code="report_not_available",
            details={"document_id": document_id, "status": document.status},
        )
    analysis = latest_analysis(document)
    if analysis is None or analysis.status != "COMPLETED":
        raise ValidationFailed(
            "No completed analysis exists for this document yet.",
            code="report_not_available",
            details={"document_id": document_id},
        )
    clauses = sorted(document.clauses, key=lambda clause: clause.clause_number)
    clauses_by_id: dict[int, Clause] = {clause.id: clause for clause in clauses}
    payload = build_report_pdf(document, analysis, clauses_by_id)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="juriscan-audit-{document.id}.pdf"'
            )
        },
    )


__all__ = ["router"]
