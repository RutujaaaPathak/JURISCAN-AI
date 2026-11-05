"""Company membership and invitation helpers shared by API modules."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from app.models import CompanyInvitation, User


def normalize_email(email: str) -> str:
    return email.strip().lower()


def generate_invitation_token() -> str:
    return secrets.token_urlsafe(32)


def hash_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def invitation_is_expired(
    invitation: CompanyInvitation, *, now: datetime | None = None
) -> bool:
    expires_at = as_utc(invitation.expires_at)
    current = now or datetime.now(timezone.utc)
    return expires_at is not None and expires_at <= current


def can_manage_company_documents(user: User) -> bool:
    return user.role == "company" and user.company_role in (
        "COMPANY_ADMIN",
        "MANAGER",
    )


def can_upload_company_documents(user: User) -> bool:
    return user.role == "company" and user.company_role in (
        "COMPANY_ADMIN",
        "MANAGER",
        "MEMBER",
    )


__all__ = [
    "as_utc",
    "can_manage_company_documents",
    "can_upload_company_documents",
    "generate_invitation_token",
    "hash_invitation_token",
    "invitation_is_expired",
    "normalize_email",
]
