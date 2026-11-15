"""Small user-account helpers shared by auth and invitation acceptance."""

from __future__ import annotations

import re

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import User

_USERNAME_FALLBACK = "user"
_USERNAME_MAX = 50


def normalize_email(email: str) -> str:
    return email.strip().lower()


def unique_username(db: Session, email: str) -> str:
    base = re.sub(r"[^a-z0-9_.-]", "", email.split("@")[0].lower()) or _USERNAME_FALLBACK
    base = base[:_USERNAME_MAX]
    candidate = base
    suffix = 1
    while db.scalar(select(User.id).where(User.username == candidate)) is not None:
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


def revoke_user_sessions(db: Session, user: User) -> int:
    """Invalidate every token issued for ``user`` by advancing its generation.

    Uses a single UPDATE expression so concurrent logout/password-change
    requests cannot lose an increment. Commit is the caller-visible revocation
    point; the refreshed ``user`` reflects the new generation for any token
    issued immediately afterwards.
    """

    db.execute(
        update(User)
        .where(User.id == user.id)
        .values(token_version=User.token_version + 1)
    )
    db.commit()
    db.refresh(user)
    return user.token_version


__all__ = ["normalize_email", "revoke_user_sessions", "unique_username"]
