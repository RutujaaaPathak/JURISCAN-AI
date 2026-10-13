"""Authenticated user settings.

Profile fields that belong to the account (full name, company organisation) live
on ``users``; analysis and notification preferences live in ``user_settings``.
Every read and write is scoped to the authenticated user resolved from the bearer
token — there is no user id in the path or body — so one account can never read
or modify another account's settings.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AuthenticatedUser, DbSession
from app.models import LawyerProfile, User, UserSettings
from app.schemas.settings import UserSettingsRead, UserSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

_PREFERENCE_FIELDS = (
    "min_severity",
    "analysis_model",
    "auto_analyze",
    "notify_email_digest",
    "notify_high_risk",
    "notify_weekly_report",
)


def _get_or_create(db: DbSession, user_id: int) -> UserSettings:
    row = db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if row is None:
        row = UserSettings(user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _effective_jurisdiction(db: DbSession, user: User, row: UserSettings) -> str | None:
    """Prefer the explicit settings value, falling back to a lawyer's saved
    professional jurisdiction so the field reflects persisted profile data."""
    if row.jurisdiction:
        return row.jurisdiction
    if user.role == "lawyer":
        profile = db.scalar(
            select(LawyerProfile).where(LawyerProfile.user_id == user.id)
        )
        if profile and profile.jurisdiction:
            return profile.jurisdiction
    return None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _serialize(db: DbSession, user: User, row: UserSettings) -> UserSettingsRead:
    return UserSettingsRead(
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        organization_name=user.organization_name,
        jurisdiction=_effective_jurisdiction(db, user, row),
        min_severity=row.min_severity,
        analysis_model=row.analysis_model,
        auto_analyze=row.auto_analyze,
        notify_email_digest=row.notify_email_digest,
        notify_high_risk=row.notify_high_risk,
        notify_weekly_report=row.notify_weekly_report,
        updated_at=row.updated_at,
    )


@router.get("", response_model=UserSettingsRead)
def read_settings(db: DbSession, user: AuthenticatedUser) -> UserSettingsRead:
    row = _get_or_create(db, user.id)
    return _serialize(db, user, row)


@router.put("", response_model=UserSettingsRead)
def update_settings(
    db: DbSession, user: AuthenticatedUser, payload: UserSettingsUpdate
) -> UserSettingsRead:
    row = _get_or_create(db, user.id)

    if payload.full_name is not None:
        user.full_name = _clean(payload.full_name)
    # Organisation is a company-account concept; ignore it for other roles so an
    # individual / lawyer / admin cannot smuggle an organisation onto the account.
    if payload.organization_name is not None and user.role == "company":
        user.organization_name = _clean(payload.organization_name)
    if payload.jurisdiction is not None:
        row.jurisdiction = _clean(payload.jurisdiction)

    for field in _PREFERENCE_FIELDS:
        value = getattr(payload, field)
        if value is not None:
            setattr(row, field, value)

    db.add(row)
    db.add(user)
    db.commit()
    db.refresh(row)
    db.refresh(user)
    return _serialize(db, user, row)


__all__ = ["router"]
