"""Document retention and legal-hold deletion guards.

Retention metadata is deliberately checked at deletion time rather than by a
background purge. This keeps explicit user deletion predictable and prevents a
scheduled job from erasing documents that are still required. Zero days (or a
null company policy with a zero system default) means no automatic expiry.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import ConflictError
from app.models import Company, Document


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def retention_until_for_upload(
    db: Session,
    *,
    company_id: int | None,
    now: datetime | None = None,
) -> datetime | None:
    """Return the retention deadline for a newly uploaded document.

    A company policy wins when present; otherwise the configured system default
    applies. ``None`` and ``0`` both mean the document has no automatic expiry.
    """

    days = None
    if company_id is not None:
        company = db.get(Company, company_id)
        if company is not None:
            days = company.retention_days
    if days is None:
        days = settings.document_retention_days
    if days is None or days <= 0:
        return None
    base = as_utc(now) or datetime.now(timezone.utc)
    return base + timedelta(days=days)


def deletion_conflict(
    document: Document, *, now: datetime | None = None
) -> ConflictError | None:
    """Return the conflict that blocks deleting ``document``, if any."""

    if document.legal_hold:
        return ConflictError(
            "This document is on legal hold and cannot be deleted.",
            code="legal_hold_active",
            details={"document_id": document.id},
        )

    current = as_utc(now) or datetime.now(timezone.utc)
    retention_until = as_utc(document.retention_until)
    if retention_until is not None and retention_until > current:
        return ConflictError(
            "This document is still within its retention period and cannot be "
            "deleted yet.",
            code="retention_active",
            details={
                "document_id": document.id,
                "retention_until": retention_until.isoformat(),
            },
        )
    return None


def ensure_document_deletable(
    document: Document, *, now: datetime | None = None
) -> None:
    conflict = deletion_conflict(document, now=now)
    if conflict is not None:
        raise conflict


def ensure_documents_deletable(
    documents: list[Document], *, now: datetime | None = None
) -> None:
    """Validate every document before the caller mutates or deletes any row."""

    for document in documents:
        ensure_document_deletable(document, now=now)


__all__ = [
    "as_utc",
    "deletion_conflict",
    "ensure_document_deletable",
    "ensure_documents_deletable",
    "retention_until_for_upload",
]
