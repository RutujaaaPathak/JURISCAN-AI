"""Self-service registration, login and session endpoints.

Passwords are hashed with PBKDF2 (stdlib) and sessions are signed HMAC tokens
(see :mod:`app.core.security`). The role assigned to an account is taken solely
from the validated registration payload on the public allow-list; ``admin`` can
never be self-selected. Authorization checks elsewhere trust the token, never
any client-supplied role hint.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.api.deps import AuthenticatedUser, DbSession
from app.config import settings
from app.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import LawyerProfile, User
from app.schemas.auth import AuthUser, LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

_USERNAME_FALLBACK = "user"
_USERNAME_MAX = 50


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _unique_username(db: DbSession, email: str) -> str:
    base = re.sub(r"[^a-z0-9_.-]", "", email.split("@")[0].lower()) or _USERNAME_FALLBACK
    base = base[:_USERNAME_MAX]
    candidate = base
    suffix = 1
    while db.scalar(select(User.id).where(User.username == candidate)) is not None:
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


def _token_response(user: User) -> dict:
    ttl = settings.access_token_ttl_seconds
    token = create_access_token(user.id, secret=settings.secret_key, ttl_seconds=ttl)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ttl,
        "user": user,
    }


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(db: DbSession, payload: RegisterRequest) -> dict:
    email = _normalize_email(payload.email)
    existing = db.scalar(select(User.id).where(func.lower(User.email) == email))
    if existing is not None:
        raise ConflictError(
            "An account with this email already exists.", code="email_taken"
        )

    user = User(
        email=email,
        username=_unique_username(db, email),
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        organization_name=(
            payload.organization_name.strip()
            if payload.organization_name and payload.organization_name.strip()
            else None
        ),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if payload.role == "lawyer":
        profile = LawyerProfile(
            user_id=user.id,
            bar_registration_number=payload.bar_registration_number.strip()
            if payload.bar_registration_number
            else None,
            jurisdiction=payload.jurisdiction.strip() if payload.jurisdiction else None,
            years_experience=payload.years_experience,
            practice_areas=[area.strip() for area in payload.practice_areas if area.strip()],
            languages=[lang.strip() for lang in payload.languages if lang.strip()],
            location=payload.location.strip() if payload.location else None,
            bio=payload.bio.strip() if payload.bio else None,
            verification_status="UNVERIFIED",
        )
        db.add(profile)
        db.commit()

    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(db: DbSession, payload: LoginRequest) -> dict:
    email = _normalize_email(payload.email)
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    # A single generic message avoids revealing whether an email is registered.
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise UnauthorizedError(
            "Invalid email or password.", code="invalid_credentials"
        )
    if not user.is_active:
        raise ForbiddenError("This account is disabled.", code="account_disabled")
    return _token_response(user)


@router.get("/me", response_model=AuthUser)
def read_current_user(user: AuthenticatedUser) -> User:
    return user


__all__ = ["router"]
