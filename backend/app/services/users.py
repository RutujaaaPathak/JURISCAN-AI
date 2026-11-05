"""Small user-account helpers shared by auth and invitation acceptance."""

from __future__ import annotations

import re

from sqlalchemy import select
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


__all__ = ["normalize_email", "unique_username"]
