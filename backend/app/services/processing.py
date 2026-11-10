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

import asyncio
import functools
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import (
    AppError,
    ConflictError,
    NotFoundError,
    ValidationFailed,
)
from app.core.logging import logger
from app.models import Analysis, Clause, Document, RiskFinding, User
from app.services.analysis import MODEL_NAME, analyze_segments
from app.services.clause_quality import assess_clause_quality
from app.services.extraction import (
    page_number_for_offset,
    page_span_payloads,
    quality_payload,
    resolve_file_type,
    validate_and_extract,
)
from app.services.legal_normalization import normalize_segments
from app.services.segmentation import segment_clauses
from app.services.storage import (
    compute_content_hash,
    delete_upload,
    save_upload,
)

_FAILED_MESSAGE = "An unexpected error occurred while processing the document."
_STALE_MESSAGE = "Processing timed out before it completed. Please retry the upload."

_processing_executor: ThreadPoolExecutor | None = None
_processing_executor_lock = threading.Lock()


def _get_processing_executor() -> ThreadPoolExecutor:
    global _processing_executor
    if _processing_executor is None:
        with _processing_executor_lock:
            if _processing_executor is None:
                _processing_executor = ThreadPoolExecutor(
                    max_workers=max(1, settings.processing_max_concurrent_jobs),
                    thread_name_prefix="juriscan-processing",
                )
    return _processing_executor


def shutdown_processing_executor(*, wait: bool = False) -> None:
    """Release the module-level processing executor (shutdown/tests)."""

    global _processing_executor
    with _processing_executor_lock:
        executor = _processing_executor
        _processing_executor = None
    if executor is not None:
        executor.shutdown(wait=wait, cancel_futures=True)


def recover_stale_documents(db: Session, *, stale_seconds: int) -> int:
    """Mark documents stuck in ``PROCESSING`` for too long as ``FAILED``.

    The update is conditional on the row still being ``PROCESSING`` at write
    time, so a worker that completes concurrently can never be overwritten by a
    stale sweep. Returns the number of documents recovered. This is best-effort
    and never raises, so a single bad row cannot block an upload.
    """

    threshold = datetime.now(timezone.utc) - timedelta(seconds=max(stale_seconds, 0))
    try:
        result = db.execute(
            update(Document)
            .where(
                Document.status == "PROCESSING",
                Document.updated_at < threshold,
            )
            .values(
                status="FAILED",
                error_message=_STALE_MESSAGE,
                updated_at=datetime.now(timezone.utc),
            )
            .execution_options(synchronize_session=False)
        )
        db.commit()
        return max(int(result.rowcount or 0), 0)
    except Exception:
        db.rollback()
        logger.exception("Failed to recover stale documents")
        return 0


def recover_stale_documents_in_new_session() -> int:
    """Run stale-document recovery with a session owned by the caller thread."""

    with SessionLocal() as db:
        return recover_stale_documents(
            db, stale_seconds=settings.processing_stale_seconds
        )


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


def delete_document(db: Session, document: Document) -> None:
    """Permanently remove a document, its results and its stored upload.

    Findings, analyses and clauses are removed explicitly (SQLite does not
    enforce ``ON DELETE CASCADE`` by default), then the row itself is deleted.
    The stored file is only removed when it lives inside the managed upload
    directory.
    """

    storage_path = document.storage_path
    _clear_results(db, document, keep_clauses=False)
    db.delete(document)
    db.commit()
    delete_upload(storage_path)


def delete_all_documents(
    db: Session, user_id: int, *, company_id: int | None = None
) -> int:
    """Permanently remove every document in the caller's deletion scope.

    Without ``company_id`` deletion is scoped to the owning user so no other
    account's data is ever touched. Company administrators/managers may pass
    their company id to remove all company documents. Findings, analyses and
    clauses are removed explicitly, all rows are committed in a single
    transaction, and stored files are removed afterwards (only those inside the
    managed upload directory). The number of deleted documents is returned.
    """

    stmt = select(Document)
    if company_id is not None:
        stmt = stmt.where(
            (Document.company_id == company_id) | (Document.user_id == user_id)
        )
    else:
        stmt = stmt.where(Document.user_id == user_id)
    documents = list(db.scalars(stmt).all())
    if not documents:
        return 0

    storage_paths = [
        document.storage_path for document in documents if document.storage_path
    ]
    for document in documents:
        _clear_results(db, document, keep_clauses=False)
        db.delete(document)
    db.commit()

    for storage_path in storage_paths:
        delete_upload(storage_path)
    return len(documents)


def _latest_completed_analysis(document: Document) -> Analysis | None:
    """Return the most recent COMPLETED analysis for ``document``, if any."""

    completed = [
        analysis for analysis in document.analyses if analysis.status == "COMPLETED"
    ]
    if not completed:
        return None
    return max(completed, key=lambda analysis: (analysis.created_at, analysis.id))


def _duplicate_conflict(
    document: Document, user: User, *, same_scope: bool | None = None
) -> ConflictError:
    """Build the duplicate-upload conflict for ``document``.

    ``same_scope`` states whether the caller shares ownership of the document
    or its company workspace; only then are any document details included, so
    another account's identical upload is never exposed. When omitted, plain
    ownership decides.
    """

    same_owner = document.user_id == user.id
    if same_scope is None:
        same_scope = same_owner
    completed = _latest_completed_analysis(document)
    details = (
        {
            "document_id": document.id,
            "analysis_id": completed.id if completed else None,
            "title": document.title,
            "filename": document.filename,
            "status": document.status,
        }
        if same_scope
        else None
    )
    if document.status == "PROCESSING":
        message = "This document is already being processed."
    elif same_scope and completed is not None:
        message = "This document has already been analyzed."
    else:
        message = "This document has already been uploaded."
    return ConflictError(
        message,
        code="duplicate_document",
        details=details,
    )


def _ensure_processing_active(db: Session, document_id: int) -> None:
    """Lock and verify that a worker still owns this document's processing run."""

    status = db.scalar(
        select(Document.status)
        .where(Document.id == document_id)
        .with_for_update()
    )
    if status != "PROCESSING":
        raise ValidationFailed(
            "Processing was interrupted before it completed. Please retry the upload.",
            code="processing_interrupted",
            details={"document_id": document_id, "status": status},
        )


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
    clause_qualities: list[dict] | None = None,
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
        normalized_text = getattr(segment, "normalized_text", None)
        normalization_changes = list(
            getattr(segment, "normalization_changes", ()) or ()
        )
        quality = (
            clause_qualities[index]
            if clause_qualities is not None and index < len(clause_qualities)
            else None
        )

        if segment.number in existing_by_number:
            clause = existing_by_number[segment.number]
            clause.heading = segment.heading
            clause.text = segment.text
            clause.normalized_text = normalized_text
            clause.normalization_changes = normalization_changes or None
            if clause_qualities is not None:
                clause.ocr_quality = quality
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
                normalized_text=normalized_text,
                normalization_changes=normalization_changes or None,
                ocr_quality=quality,
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
        if extracted.quality_warnings:
            logger.warning(
                "OCR quality warnings for document %s: %s",
                document_id,
                " ".join(extracted.quality_warnings),
            )
        segments = normalize_segments(segment_clauses(extracted.text))
        if not segments:
            raise ValidationFailed(
                "No clauses could be identified in the document.",
                code="no_clauses",
            )
        clause_qualities = assess_clause_quality(
            segments, extracted.pages, extracted.ocr_line_spans
        )
        review_clause_indexes = {
            index
            for index, quality in enumerate(clause_qualities)
            if quality.get("requires_verification")
        }
        result = analyze_segments(segments)
        review_finding_count = sum(
            1
            for finding in result.findings
            if finding.segment_index in review_clause_indexes
        )

        # Acquire a short-lived row lock before writing results. A stale sweep
        # may have finalized this document while extraction/OCR was running; if
        # so, abort rather than overwrite the terminal FAILED state.
        _ensure_processing_active(db, document_id)

        stored_path = save_upload(data, filename)
        document.storage_path = stored_path
        document.file_type = extracted.file_type
        document.mime_type = content_type
        document.page_count = extracted.page_count
        document.word_count = extracted.word_count
        document.language = extracted.language
        document.text_content = extracted.text
        document.page_spans = page_span_payloads(extracted.pages)
        document.ocr_quality = quality_payload(extracted.ocr_quality)
        document.quality_warnings = extracted.quality_warnings or None
        document.extracted_at = extracted.extracted_at
        document.error_message = None
        db.flush()

        clauses = persist_clauses(
            db,
            document,
            segments,
            extracted.pages,
            result,
            clause_qualities=clause_qualities,
        )

        now = extracted.extracted_at
        summary = result.summary
        if extracted.quality_warnings:
            notice = " ".join(extracted.quality_warnings)
            summary = f"{summary}\n\nOCR quality notice: {notice}"
        if review_clause_indexes:
            summary = (
                f"{summary}\n\nOCR verification notice: "
                f"{len(review_clause_indexes)} clause(s) came from low-confidence "
                f"OCR; {review_finding_count} finding(s) are marked for manual "
                "verification."
            )
        analysis = Analysis(
            document_id=document.id,
            model_name=MODEL_NAME,
            status="COMPLETED",
            risk_score=result.risk_score,
            summary=summary,
            started_at=now,
            completed_at=now,
        )
        db.add(analysis)
        db.flush()

        for finding in result.findings:
            clause = clauses[finding.segment_index]
            quality = clause_qualities[finding.segment_index]
            requires_review = bool(quality.get("requires_verification"))
            confidence = quality.get("confidence")
            review_reason = None
            if requires_review:
                if confidence is None:
                    review_reason = (
                        f"Clause {clause.clause_number} was read from OCR but its "
                        "confidence is unavailable. Verify the quoted wording before "
                        "relying on this finding."
                    )
                else:
                    review_reason = (
                        f"Clause {clause.clause_number} was read from OCR with "
                        f"{confidence:.0%} confidence. Verify the quoted wording "
                        "before relying on this finding."
                    )
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
                    requires_review=requires_review,
                    review_reason=review_reason,
                    ocr_confidence=confidence,
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
    force: bool = False,
    company_id: int | None = None,
) -> Document:
    """Entry point used by the upload endpoint.

    When an identical document already exists (matched by content hash) a new
    row is never created. Behaviour depends on the caller:

    * ``force=True`` (or a document whose previous run failed / never produced a
      completed analysis) re-analyzes the existing record in place.
    * an already-analyzed document is reported back as a conflict that carries
      the ``document_id`` and ``analysis_id`` so the client can offer to open
      the existing analysis or re-run it.
    """

    recover_stale_documents(db, stale_seconds=settings.processing_stale_seconds)

    file_type = resolve_file_type(filename, content_type)
    document_title = (title or "").strip() or Path(filename).stem or "Untitled document"
    content_hash = compute_content_hash(data)

    existing = db.scalar(
        select(Document).where(Document.content_hash == content_hash)
    )
    if existing is not None:
        same_owner = existing.user_id == user.id
        same_company = (
            company_id is not None and existing.company_id == company_id
        )
        if company_id is not None and existing.company_id is None:
            # When a company user uploads a previously unassigned contract, attach it
            # to their company workspace so it automatically appears in audit reports.
            existing.company_id = company_id
            db.commit()
            db.refresh(existing)
            same_company = True
        elif company_id is not None and not same_company:
            # If the document was uploaded by another member of this same company,
            # unify its company scope.
            prev_owner = db.get(User, existing.user_id)
            if prev_owner and prev_owner.company_id == company_id:
                existing.company_id = company_id
                db.commit()
                db.refresh(existing)
                same_company = True

        same_scope = same_owner or same_company
        completed = _latest_completed_analysis(existing)
        if existing.status == "PROCESSING":
            raise _duplicate_conflict(existing, user, same_scope=same_scope)
        if same_scope and (force or completed is None):
            # Re-analyze in place when explicitly requested, after a previous
            # failure, or when the stored record never produced a completed
            # analysis. This is what lets a re-uploaded PDF be analyzed again.
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
            # Another user's (or company's) identical document is never touched
            # or exposed.
            raise _duplicate_conflict(existing, user, same_scope=same_scope)
    else:
        document = Document(
            user_id=user.id,
            company_id=company_id,
            title=document_title,
            filename=filename,
            file_type=file_type,
            mime_type=content_type,
            content_hash=content_hash,
            status="PROCESSING",
        )
        db.add(document)

    try:
        db.commit()
    except IntegrityError as exc:
        # Two identical uploads can race between the SELECT above and INSERT.
        # The unique content_hash constraint lets one win; report the other as
        # the same duplicate conflict a sequential upload would receive.
        db.rollback()
        existing = db.scalar(
            select(Document).where(Document.content_hash == content_hash)
        )
        if existing is not None:
            raced_same_scope = existing.user_id == user.id or (
                company_id is not None and existing.company_id == company_id
            )
            raise _duplicate_conflict(
                existing, user, same_scope=raced_same_scope
            ) from None
        raise ValidationFailed(
            "The document could not be saved because of a concurrent upload.",
            code="processing_failed",
        ) from exc

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


def _process_upload_worker(
    *,
    user_id: int,
    data: bytes,
    filename: str,
    content_type: str | None,
    title: str | None,
    max_size_bytes: int,
    force: bool,
    company_id: int | None = None,
) -> int:
    """Run one upload in a worker thread with a session it exclusively owns."""

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            raise NotFoundError(
                "The user account no longer exists.",
                code="user_not_found",
                details={"user_id": user_id},
            )
        document = process_upload(
            db,
            user=user,
            data=data,
            filename=filename,
            content_type=content_type,
            title=title,
            max_size_bytes=max_size_bytes,
            force=force,
            company_id=company_id,
        )
        return document.id


async def process_upload_async(
    *,
    user_id: int,
    data: bytes,
    filename: str,
    content_type: str | None,
    title: str | None,
    max_size_bytes: int,
    force: bool = False,
    company_id: int | None = None,
) -> int:
    """Run :func:`process_upload` off the event loop and return its document id."""

    loop = asyncio.get_running_loop()
    worker = functools.partial(
        _process_upload_worker,
        user_id=user_id,
        data=data,
        filename=filename,
        content_type=content_type,
        title=title,
        max_size_bytes=max_size_bytes,
        force=force,
        company_id=company_id,
    )
    return await loop.run_in_executor(_get_processing_executor(), worker)


__all__ = [
    "delete_all_documents",
    "delete_document",
    "persist_clauses",
    "process_upload",
    "process_upload_async",
    "recover_stale_documents",
    "recover_stale_documents_in_new_session",
    "run_processing",
    "shutdown_processing_executor",
    "sync_legacy_clause_hierarchy",
]
