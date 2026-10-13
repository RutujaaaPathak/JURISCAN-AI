"""Document processing lifecycle: status transitions and extraction errors.

The upload endpoint calls :func:`process_upload`, which:

1. recovers documents that were left in ``PROCESSING`` (stale),
2. resolves duplicate uploads (completed documents are protected from
   reprocessing; failed ones are retried in place),
3. persists a ``PROCESSING`` record, then
4. runs extraction + segmentation + analysis and finalises to ``PROCESSED``,
   or records ``FAILED`` with an error message.

Keeping the status handling here means failures can never leave a document
stuck in ``PROCESSING``: the surrounding ``try/except`` always finalises it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import AppError, ConflictError, ValidationFailed
from app.models import Analysis, Clause, Document, RiskFinding, User
from app.services.analysis import MODEL_NAME, analyze_segments
from app.services.extraction import (
    page_number_for_offset,
    resolve_file_type,
    validate_and_extract,
)
from app.services.segmentation import segment_clauses
from app.services.storage import (
    compute_content_hash,
    delete_upload,
    save_upload,
)

_FAILED_MESSAGE = "An unexpected error occurred while processing the document."


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def recover_stale_documents(db: Session, *, stale_seconds: int) -> int:
    """Mark documents stuck in ``PROCESSING`` for too long as ``FAILED``.

    Returns the number of documents recovered. This is best-effort and never
    raises, so a single bad row cannot block an upload.
    """

    threshold = datetime.now(timezone.utc) - timedelta(seconds=max(stale_seconds, 0))
    stuck = db.scalars(
        select(Document).where(Document.status == "PROCESSING")
    ).all()
    recovered = 0
    for document in stuck:
        updated = _as_utc(document.updated_at)
        if updated is not None and updated < threshold:
            document.status = "FAILED"
            document.error_message = (
                "Processing timed out before it completed. Please retry the upload."
            )
            recovered += 1
    if recovered:
        db.commit()
    return recovered


def _clear_results(
    db: Session, document: Document, *, keep_clauses: bool = True
) -> None:
    for analysis in list(document.analyses):
        for finding in list(analysis.risk_findings):
            db.delete(finding)
        db.delete(analysis)
    if not keep_clauses:
        for clause in list(document.clauses):
            db.delete(clause)


def _prepare_retry(
    db: Session,
    document: Document,
    *,
    title: str,
    filename: str,
    content_type: str | None,
    file_type: str,
) -> None:
    """Reset a failed document so the same row can be processed again."""

    delete_upload(document.storage_path)
    _clear_results(db, document, keep_clauses=True)
    document.title = title
    document.filename = filename
    document.file_type = file_type
    document.mime_type = content_type
    document.storage_path = None
    document.page_count = None
    document.word_count = None
    document.language = None
    document.text_content = None
    document.extracted_at = None
    document.error_message = None
    document.status = "PROCESSING"


def _finalize_failed(db: Session, document_id: int, message: str) -> None:
    db.rollback()
    document = db.get(Document, document_id)
    if document is None:
        return
    document.status = "FAILED"
    document.error_message = message
    document.storage_path = None
    db.commit()


def persist_clauses(
    db: Session,
    document: Document,
    segments: list,
    pages: list,
    result: Any,
) -> list[Clause]:
    """Persist segmented clauses for ``document``, updating existing rows by
    clause_number to reuse IDs, preserve risk-finding references, prevent duplicate
    clauses during retries, and establish within-document parent hierarchy."""

    existing_by_number: dict[int, Clause] = {
        clause.clause_number: clause for clause in document.clauses
    }

    clauses: list[Clause] = []
    # Step 1: Update existing clauses or insert new ones
    for index, segment in enumerate(segments):
        page_num = page_number_for_offset(pages, segment.start_offset)
        clause_type = (
            result.clause_type_by_index.get(index)
            if hasattr(result, "clause_type_by_index") and result.clause_type_by_index
            else None
        )
        risk_level = (
            result.risk_level_by_index.get(index)
            if hasattr(result, "risk_level_by_index") and result.risk_level_by_index
            else None
        )

        if segment.number in existing_by_number:
            clause = existing_by_number[segment.number]
            clause.heading = segment.heading
            clause.text = segment.text
            clause.start_offset = segment.start_offset
            clause.end_offset = segment.end_offset
            clause.page_number = page_num
            clause.label = segment.label
            clause.level = segment.level
            if clause_type is not None:
                clause.clause_type = clause_type
            if risk_level is not None:
                clause.risk_level = risk_level
        else:
            clause = Clause(
                document_id=document.id,
                clause_number=segment.number,
                heading=segment.heading,
                text=segment.text,
                start_offset=segment.start_offset,
                end_offset=segment.end_offset,
                page_number=page_num,
                clause_type=clause_type,
                risk_level=risk_level,
                label=segment.label,
                level=segment.level,
            )
            db.add(clause)
        clauses.append(clause)

    # Step 2: Remove any excess clauses that no longer exist in the document
    new_numbers = {segment.number for segment in segments}
    for old_num, old_clause in list(existing_by_number.items()):
        if old_num not in new_numbers:
            db.delete(old_clause)

    # Flush to ensure newly added clauses receive primary keys
    db.flush()

    # Step 3: Link parent-child hierarchy within the current document
    for index, segment in enumerate(segments):
        if segment.parent is not None:
            if 0 <= segment.parent < len(clauses):
                parent_clause = clauses[segment.parent]
                if parent_clause.document_id != document.id:
                    raise ValueError("Parent clause must belong to the same document.")
                clauses[index].parent_id = parent_clause.id
            else:
                clauses[index].parent_id = None
        else:
            clauses[index].parent_id = None

    db.flush()
    return clauses


def sync_legacy_clause_hierarchy(
    db: Session,
    document: Document,
) -> list[Clause]:
    """Backfill hierarchy metadata (label, level, parent_id, offsets) for legacy
    clauses in ``document`` using deterministic segmentation."""

    if not document.text_content:
        return list(document.clauses)

    segments = segment_clauses(document.text_content)
    if not segments:
        return list(document.clauses)

    clauses_by_number = {c.clause_number: c for c in document.clauses}
    ordered_clauses: list[Clause] = []

    for segment in segments:
        if segment.number in clauses_by_number:
            clause = clauses_by_number[segment.number]
            clause.label = segment.label
            clause.level = segment.level
            if clause.start_offset is None:
                clause.start_offset = segment.start_offset
            if clause.end_offset is None:
                clause.end_offset = segment.end_offset
            ordered_clauses.append(clause)

    for index, segment in enumerate(segments):
        if index < len(ordered_clauses):
            clause = ordered_clauses[index]
            if segment.parent is not None and 0 <= segment.parent < len(ordered_clauses):
                parent_clause = ordered_clauses[segment.parent]
                if parent_clause.document_id != document.id:
                    raise ValueError("Parent clause must belong to the same document.")
                clause.parent_id = parent_clause.id
            else:
                clause.parent_id = None

    db.flush()
    return ordered_clauses


def run_processing(
    db: Session,
    document: Document,
    *,
    data: bytes,
    filename: str,
    content_type: str | None,
    title: str,
    max_size_bytes: int,
) -> Document:
    """Extract, segment and analyse ``data`` into ``document`` and finalise."""

    document_id = document.id
    stored_path: str | None = None
    try:
        extracted = validate_and_extract(
            data, filename, content_type, max_size_bytes
        )
        segments = segment_clauses(extracted.text)
        if not segments:
            raise ValidationFailed(
                "No clauses could be identified in the document.",
                code="no_clauses",
            )
        result = analyze_segments(segments)

        stored_path = save_upload(data, filename)
        document.storage_path = stored_path
        document.file_type = extracted.file_type
        document.mime_type = content_type
        document.page_count = extracted.page_count
        document.word_count = extracted.word_count
        document.language = extracted.language
        document.text_content = extracted.text
        document.extracted_at = extracted.extracted_at
        document.error_message = None
        db.flush()

        clauses = persist_clauses(
            db,
            document,
            segments,
            extracted.pages,
            result,
        )

        now = extracted.extracted_at
        analysis = Analysis(
            document_id=document.id,
            model_name=MODEL_NAME,
            status="COMPLETED",
            risk_score=result.risk_score,
            summary=result.summary,
            started_at=now,
            completed_at=now,
        )
        db.add(analysis)
        db.flush()

        for finding in result.findings:
            clause = clauses[finding.segment_index]
            db.add(
                RiskFinding(
                    analysis_id=analysis.id,
                    clause_id=clause.id,
                    rule_code=finding.rule_code,
                    severity=finding.severity,
                    title=finding.title,
                    description=finding.description,
                    recommendation=finding.recommendation,
                    citation=finding.citation,
                )
            )

        document.status = "PROCESSED"
        document.error_message = None
        db.commit()
    except AppError as exc:
        if stored_path:
            delete_upload(stored_path)
        _finalize_failed(db, document_id, exc.message)
        raise
    except Exception as exc:  # pragma: no cover - defensive
        if stored_path:
            delete_upload(stored_path)
        _finalize_failed(db, document_id, _FAILED_MESSAGE)
        raise ValidationFailed(
            "The document could not be processed.",
            code="processing_failed",
        ) from exc

    db.refresh(document)
    return document


def process_upload(
    db: Session,
    *,
    user: User,
    data: bytes,
    filename: str,
    content_type: str | None,
    title: str | None,
    max_size_bytes: int,
) -> Document:
    """Entry point used by the upload endpoint."""

    recover_stale_documents(db, stale_seconds=settings.processing_stale_seconds)

    file_type = resolve_file_type(filename, content_type)
    document_title = (title or "").strip() or Path(filename).stem or "Untitled document"
    content_hash = compute_content_hash(data)

    existing = db.scalar(
        select(Document).where(Document.content_hash == content_hash)
    )
    if existing is not None:
        if existing.user_id == user.id:
            details = {"document_id": existing.id, "title": existing.title}
        else:
            details = None
        if existing.status == "PROCESSED":
            raise ConflictError(
                "This document has already been uploaded.",
                code="duplicate_document",
                details=details,
            )
        if existing.status == "PROCESSING":
            raise ConflictError(
                "This document is already being processed.",
                code="duplicate_document",
                details=details,
            )
        # A FAILED document is retried in place to avoid duplicate records.
        document = existing
        _prepare_retry(
            db,
            document,
            title=document_title,
            filename=filename,
            content_type=content_type,
            file_type=file_type,
        )
    else:
        document = Document(
            user_id=user.id,
            title=document_title,
            filename=filename,
            file_type=file_type,
            mime_type=content_type,
            content_hash=content_hash,
            status="PROCESSING",
        )
        db.add(document)

    db.commit()
    db.refresh(document)
    return run_processing(
        db,
        document,
        data=data,
        filename=filename,
        content_type=content_type,
        title=document_title,
        max_size_bytes=max_size_bytes,
    )


__all__ = [
    "persist_clauses",
    "process_upload",
    "recover_stale_documents",
    "run_processing",
    "sync_legacy_clause_hierarchy",
]
