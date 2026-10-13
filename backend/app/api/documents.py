"""Document upload, listing, detail and overview-statistics endpoints."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.config import settings
from app.core.exceptions import NotFoundError, ValidationFailed
from app.models import Analysis, Case, CaseDocument, Clause, Document, RiskFinding
from app.schemas.documents import (
    AnalysisDetail,
    ClauseRead,
    DocumentDetail,
    DocumentListResponse,
    DocumentSummary,
    OverviewStats,
    RiskFindingRead,
)
from app.services.analysis import RULES
from app.services.processing import process_upload

router = APIRouter(tags=["documents"])

RULE_CATEGORY = {rule.code: rule.category for rule in RULES}
RISK_ORDER = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


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


def _document_query():
    return select(Document).options(
        selectinload(Document.clauses),
        selectinload(Document.analyses).selectinload(Analysis.risk_findings),
    )


def _latest_analysis(document: Document) -> Analysis | None:
    if not document.analyses:
        return None
    return max(document.analyses, key=lambda analysis: (analysis.created_at, analysis.id))


def _summary_payload(document: Document) -> dict:
    analysis = _latest_analysis(document)
    findings = analysis.risk_findings if analysis else []
    return {
        "id": document.id,
        "title": document.title,
        "filename": document.filename,
        "file_type": document.file_type,
        "status": document.status,
        "page_count": document.page_count,
        "word_count": document.word_count,
        "language": document.language,
        "extracted_at": document.extracted_at,
        "error_message": document.error_message,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "analysis_id": analysis.id if analysis else None,
        "analysis_status": analysis.status if analysis else None,
        "model_name": analysis.model_name if analysis else None,
        "risk_score": analysis.risk_score if analysis else None,
        "risk_level": _risk_band(analysis.risk_score) if analysis else None,
        "finding_count": len(findings),
        "high_risk_count": sum(
            1 for finding in findings if finding.severity in ("HIGH", "CRITICAL")
        ),
    }


def _finding_payload(finding: RiskFinding, clause: Clause | None) -> dict:
    return {
        "id": finding.id,
        "analysis_id": finding.analysis_id,
        "clause_id": finding.clause_id,
        "rule_code": finding.rule_code,
        "severity": finding.severity,
        "title": finding.title,
        "description": finding.description,
        "recommendation": finding.recommendation,
        "citation": finding.citation,
        "clause_number": clause.clause_number if clause else None,
        "clause_heading": clause.heading if clause else None,
        "clause_page": clause.page_number if clause else None,
        "clause_label": clause.label if clause else None,
        "clause_level": clause.level if clause else None,
        "created_at": finding.created_at,
        "updated_at": finding.updated_at,
    }


def _analysis_payload(analysis: Analysis, clauses_by_id: dict[int, Clause]) -> dict:
    return {
        "id": analysis.id,
        "document_id": analysis.document_id,
        "model_name": analysis.model_name,
        "status": analysis.status,
        "risk_score": analysis.risk_score,
        "summary": analysis.summary,
        "started_at": analysis.started_at,
        "completed_at": analysis.completed_at,
        "created_at": analysis.created_at,
        "updated_at": analysis.updated_at,
        "findings": [
            _finding_payload(finding, clauses_by_id.get(finding.clause_id or -1))
            for finding in analysis.risk_findings
        ],
    }


def _page_payloads(document: Document) -> list[dict]:
    """Derive source-page character ranges from the persisted clause page numbers.

    Only paginated formats produce page numbers on clauses, so DOCX/TXT yield an
    empty list and the viewer falls back to a single unpaginated section. Page
    ranges are made contiguous (the first starts at 0 and the last ends at the
    length of the text) so the client can slice the text without gaps.
    """

    text = document.text_content or ""
    if not text:
        return []

    paginated = [clause for clause in document.clauses if clause.page_number is not None]
    paginated.sort(
        key=lambda clause: (clause.start_offset or 0, clause.id)
    )

    transitions: list[tuple[int, int]] = []
    for clause in paginated:
        offset = clause.start_offset or 0
        if not transitions or transitions[-1][0] != clause.page_number:
            transitions.append((clause.page_number, offset))
    if not transitions:
        return []

    pages: list[dict] = []
    for index, (number, start) in enumerate(transitions):
        end = transitions[index + 1][1] if index + 1 < len(transitions) else len(text)
        pages.append(
            {
                "page_number": number,
                "start_offset": 0 if index == 0 else start,
                "end_offset": end,
            }
        )
    return pages


def _detail_payload(document: Document) -> dict:
    clauses = sorted(document.clauses, key=lambda clause: clause.clause_number)
    clauses_by_id = {clause.id: clause for clause in clauses}
    analysis = _latest_analysis(document)
    payload = _summary_payload(document)
    payload["text_content"] = document.text_content
    payload["pages"] = _page_payloads(document)
    payload["clauses"] = [ClauseRead.model_validate(clause).model_dump() for clause in clauses]
    payload["analysis"] = (
        _analysis_payload(analysis, clauses_by_id) if analysis else None
    )
    return payload


def _shared_document_ids(user_id: int):
    """Document ids the user may read because they are linked to a case they
    posted or are the assigned lawyer for. This is the authorization rule that
    lets an accepted lawyer open a client's attached documents without granting
    access to any other document."""

    return (
        select(CaseDocument.document_id)
        .join(Case, Case.id == CaseDocument.case_id)
        .where(
            or_(
                Case.posted_by_user_id == user_id,
                Case.assigned_lawyer_id == user_id,
            )
        )
    )


def _get_document_or_404(db: DbSession, document_id: int, user_id: int) -> Document:
    document = db.scalar(
        _document_query().where(
            Document.id == document_id,
            or_(
                Document.user_id == user_id,
                Document.id.in_(_shared_document_ids(user_id)),
            ),
        )
    )
    if document is None:
        raise NotFoundError(
            f"Document {document_id} was not found.",
            code="document_not_found",
            details={"document_id": document_id},
        )
    return document


async def _read_upload(file: UploadFile, max_bytes: int) -> bytes:
    """Read an upload while enforcing the size limit to avoid buffering
    unbounded data in memory before validation."""

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValidationFailed(
                f"The file exceeds the maximum size of "
                f"{max_bytes // (1024 * 1024)} MB.",
                code="file_too_large",
                details={"max_size_mb": max_bytes // (1024 * 1024)},
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/documents", response_model=DocumentDetail, status_code=201)
async def upload_document(
    db: DbSession,
    user: CurrentUser,
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=255),
) -> dict:
    filename = Path(file.filename or "document").name
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    data = await _read_upload(file, max_bytes)
    if not data:
        raise ValidationFailed("The uploaded file is empty.", code="empty_file")

    document = process_upload(
        db,
        user=user,
        data=data,
        filename=filename,
        content_type=file.content_type,
        title=title,
        max_size_bytes=max_bytes,
    )

    document = _get_document_or_404(db, document.id, user.id)
    return _detail_payload(document)


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(
    db: DbSession,
    user: CurrentUser,
    q: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, max_length=16),
    file_type: str | None = Query(default=None, max_length=16),
    risk_level: str | None = Query(default=None, max_length=16),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    stmt = _document_query().where(Document.user_id == user.id)
    if q and q.strip():
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Document.title).like(pattern),
                func.lower(Document.filename).like(pattern),
            )
        )
    if status:
        stmt = stmt.where(Document.status == status.upper())
    if file_type:
        stmt = stmt.where(Document.file_type == file_type.lower())

    stmt = stmt.order_by(Document.created_at.desc(), Document.id.desc())
    documents = list(db.scalars(stmt).all())

    summaries = [_summary_payload(document) for document in documents]
    if risk_level:
        wanted = risk_level.upper()
        summaries = [summary for summary in summaries if summary["risk_level"] == wanted]

    total = len(summaries)
    page = summaries[offset : offset + limit]
    return {"items": page, "total": total}


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(db: DbSession, user: CurrentUser, document_id: int) -> dict:
    document = _get_document_or_404(db, document_id, user.id)
    return _detail_payload(document)


@router.get("/analyses/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(db: DbSession, user: CurrentUser, analysis_id: int) -> dict:
    analysis = db.scalar(
        select(Analysis)
        .options(selectinload(Analysis.risk_findings))
        .join(Document, Analysis.document_id == Document.id)
        .where(
            Analysis.id == analysis_id,
            or_(
                Document.user_id == user.id,
                Document.id.in_(_shared_document_ids(user.id)),
            ),
        )
    )
    if analysis is None:
        raise NotFoundError(
            f"Analysis {analysis_id} was not found.",
            code="analysis_not_found",
            details={"analysis_id": analysis_id},
        )
    clauses = db.scalars(
        select(Clause).where(Clause.document_id == analysis.document_id)
    ).all()
    clauses_by_id = {clause.id: clause for clause in clauses}
    return _analysis_payload(analysis, clauses_by_id)


@router.get("/stats/overview", response_model=OverviewStats)
def overview_stats(db: DbSession, user: CurrentUser) -> dict:
    documents = list(
        db.scalars(_document_query().where(Document.user_id == user.id)).all()
    )
    total = len(documents)
    processed = sum(1 for document in documents if document.status == "PROCESSED")
    processing = sum(
        1
        for document in documents
        if document.status in ("PENDING", "PROCESSING")
    )
    failed = sum(1 for document in documents if document.status == "FAILED")

    latest = [_latest_analysis(document) for document in documents]
    risk_scores = [
        analysis.risk_score
        for analysis in latest
        if analysis is not None and analysis.risk_score is not None
    ]
    avg_risk = round(sum(risk_scores) / len(risk_scores), 1) if risk_scores else 0.0

    risk_distribution = {level: 0 for level in RISK_ORDER}
    findings: list[RiskFinding] = []
    for analysis in latest:
        if analysis is None:
            continue
        if analysis.risk_score is not None:
            band = _risk_band(analysis.risk_score)
            if band is not None:
                risk_distribution[band] += 1
        findings.extend(analysis.risk_findings)

    high_risk_findings = sum(
        1 for finding in findings if finding.severity in ("HIGH", "CRITICAL")
    )
    category_counter = Counter(RULE_CATEGORY.get(finding.rule_code, "Other") for finding in findings)
    category_counts = [
        {"category": category, "count": count}
        for category, count in category_counter.most_common()
    ]

    today = datetime.now(timezone.utc).date()
    per_day = Counter(
        document.created_at.date()
        for document in documents
        if document.created_at is not None
    )
    upload_trend = [
        {
            "date": (today - timedelta(days=offset)).isoformat(),
            "count": per_day.get(today - timedelta(days=offset), 0),
        }
        for offset in range(6, -1, -1)
    ]

    return {
        "total_documents": total,
        "processed": processed,
        "processing": processing,
        "failed": failed,
        "avg_risk_score": avg_risk,
        "high_risk_findings": high_risk_findings,
        "risk_distribution": risk_distribution,
        "category_counts": category_counts,
        "upload_trend": upload_trend,
    }


__all__ = ["router"]
