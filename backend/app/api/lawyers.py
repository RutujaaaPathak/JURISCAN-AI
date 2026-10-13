"""Lawyer profile and verification-state endpoints.

Verification here only records the lawyer's own submission state. No reviewer,
document checks or third-party bar-registry integration exists, so the platform
never claims a profile is independently verified.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, LawyerUser
from app.core.exceptions import NotFoundError
from app.models import CASE_CATEGORIES, LawyerProfile, User

from app.schemas.lawyers import (
    LawyerDirectoryEntry,
    LawyerDirectoryResponse,
    LawyerProfileRead,
    LawyerProfileUpdate,
)

router = APIRouter(tags=["lawyers"])


def _get_or_create_profile(db: DbSession, user_id: int) -> LawyerProfile:
    profile = db.scalar(select(LawyerProfile).where(LawyerProfile.user_id == user_id))
    if profile is None:
        profile = LawyerProfile(user_id=user_id, verification_status="UNVERIFIED")
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _is_complete(profile: LawyerProfile) -> bool:
    return bool(
        profile.bar_registration_number
        and profile.jurisdiction
        and profile.years_experience is not None
        and profile.practice_areas
        and profile.bio
    )


def _payload(profile: LawyerProfile, full_name: str | None) -> dict:
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "full_name": full_name,
        "bar_registration_number": profile.bar_registration_number,
        "jurisdiction": profile.jurisdiction,
        "years_experience": profile.years_experience,
        "practice_areas": profile.practice_areas or [],
        "languages": profile.languages or [],
        "location": profile.location,
        "bio": profile.bio,
        "consultation_modes": profile.consultation_modes or [],
        "fee_structure": profile.fee_structure,
        "photo_url": profile.photo_url,
        "availability": profile.availability,
        "verification_status": profile.verification_status,
        "verification_notes": profile.verification_notes,
        "profile_complete": _is_complete(profile),
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


@router.get("/lawyer/profile", response_model=LawyerProfileRead)
def get_lawyer_profile(db: DbSession, user: LawyerUser) -> dict:
    profile = _get_or_create_profile(db, user.id)
    return _payload(profile, user.full_name)


@router.put("/lawyer/profile", response_model=LawyerProfileRead)
def update_lawyer_profile(
    db: DbSession, user: LawyerUser, payload: LawyerProfileUpdate
) -> dict:
    profile = _get_or_create_profile(db, user.id)
    data = payload.model_dump(exclude_unset=True)

    full_name = data.pop("full_name", None)
    if full_name is not None:
        stripped = full_name.strip()
        user.full_name = stripped or None

    for field, value in data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    if full_name is not None:
        db.refresh(user)
    return _payload(profile, user.full_name)


@router.post("/lawyer/profile/verification", response_model=LawyerProfileRead)
def submit_for_verification(db: DbSession, user: LawyerUser) -> dict:
    profile = _get_or_create_profile(db, user.id)
    # Only move forward from an unverified or rejected state. A manual review
    # step will eventually consume this; until then the status stays PENDING and
    # nothing is presented to clients as verified.
    if profile.verification_status in ("UNVERIFIED", "REJECTED"):
        profile.verification_status = "PENDING"
        profile.verification_notes = (
            "Submission recorded. Automated or manual verification review is not "
            "implemented yet, so this profile is not independently verified."
        )
        db.commit()
        db.refresh(profile)
    return _payload(profile, user.full_name)


def _directory_entry(profile: LawyerProfile, user: User | None) -> dict:
    return {
        "user_id": profile.user_id,
        "full_name": (user.full_name if user else None),
        "jurisdiction": profile.jurisdiction,
        "years_experience": profile.years_experience,
        "practice_areas": profile.practice_areas or [],
        "languages": profile.languages or [],
        "location": profile.location,
        "bio": profile.bio,
        "consultation_modes": profile.consultation_modes or [],
        "fee_structure": profile.fee_structure,
        "availability": profile.availability,
        "photo_url": profile.photo_url,
        "verification_status": profile.verification_status,
        "profile_complete": _is_complete(profile),
    }


@router.get("/lawyers", response_model=LawyerDirectoryResponse)
def browse_lawyers(
    db: DbSession,
    user: CurrentUser,
    q: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=32),
    location: str | None = Query(default=None, max_length=128),
    min_experience: int | None = Query(default=None, ge=0, le=80),
    consultation_mode: str | None = Query(default=None, max_length=32),
    verified_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Browse lawyer profiles. Filtering is done in Python because practice areas
    and consultation modes are stored as JSON lists, where a portable SQL filter
    differs between SQLite and PostgreSQL. The directory is small; this keeps the
    behaviour identical across both engines. Only users who have created a lawyer
    profile appear."""

    rows = db.execute(
        select(LawyerProfile, User)
        .join(User, User.id == LawyerProfile.user_id)
        .order_by(LawyerProfile.id)
    ).all()

    wanted_category = (category or "").strip().lower()
    if wanted_category and wanted_category != "all" and wanted_category not in CASE_CATEGORIES:
        wanted_category = ""

    needle = (q or "").strip().lower()
    location_needle = (location or "").strip().lower()
    mode_needle = (consultation_mode or "").strip().lower()

    entries: list[dict] = []
    for profile, account in rows:
        practice = [str(item).lower() for item in (profile.practice_areas or [])]
        modes = [str(item).lower() for item in (profile.consultation_modes or [])]
        languages = [str(item).lower() for item in (profile.languages or [])]

        if wanted_category and wanted_category not in practice:
            continue
        if verified_only and profile.verification_status != "VERIFIED":
            continue
        if min_experience is not None and (
            profile.years_experience is None or profile.years_experience < min_experience
        ):
            continue
        if mode_needle and mode_needle not in modes:
            continue
        if location_needle and location_needle not in (
            (profile.location or "").lower()
            + " "
            + (profile.jurisdiction or "").lower()
        ):
            continue
        if needle:
            haystack = " ".join(
                [
                    (account.full_name or "").lower(),
                    (profile.bio or "").lower(),
                    (profile.location or "").lower(),
                    (profile.jurisdiction or "").lower(),
                    " ".join(practice),
                    " ".join(languages),
                ]
            )
            if needle not in haystack:
                continue

        entries.append(_directory_entry(profile, account))

    # Verified profiles surface first, then most experience.
    entries.sort(
        key=lambda entry: (
            entry["verification_status"] != "VERIFIED",
            -(entry["years_experience"] or 0),
        )
    )
    return {"items": entries[offset : offset + limit], "total": len(entries)}


@router.get("/lawyers/{user_id}", response_model=LawyerDirectoryEntry)
def get_lawyer_directory_entry(db: DbSession, user: CurrentUser, user_id: int) -> dict:
    row = db.execute(
        select(LawyerProfile, User)
        .join(User, User.id == LawyerProfile.user_id)
        .where(LawyerProfile.user_id == user_id)
    ).first()
    if row is None:
        raise NotFoundError(
            f"Lawyer {user_id} was not found.",
            code="lawyer_not_found",
            details={"user_id": user_id},
        )
    profile, account = row
    return _directory_entry(profile, account)


__all__ = ["router"]
