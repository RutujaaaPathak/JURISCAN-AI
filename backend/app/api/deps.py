from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_db
from app.core.exceptions import ForbiddenError
from app.models import USER_ROLES, User

DbSession = Annotated[Session, Depends(get_db)]

# Authentication is not implemented yet, so uploads are attributed to a single
# default workspace user. This is created on demand.
DEFAULT_USER_EMAIL = "demo@juriscan.ai"
DEFAULT_USER_USERNAME = "demo-reviewer"
DEFAULT_USER_FULL_NAME = "Demo Reviewer"


def _resolve_preview_role(requested: str | None) -> str | None:
    """Return the requested workspace role for a development preview request.

    This is intentionally NOT authentication: it performs no credential check
    and only takes effect outside production. It exists so the single demo user
    can exercise role-specific endpoints while an auth layer is still missing.
    In production the requested role is always ignored.
    """

    if not requested or settings.app_env == "production":
        return None
    if requested not in USER_ROLES:
        return None
    return requested


def get_current_user(
    db: DbSession,
    x_developer_role: Annotated[str | None, Header(alias="X-Developer-Role")] = None,
) -> User:
    user = db.scalar(select(User).where(User.email == DEFAULT_USER_EMAIL))
    if user is None:
        user = User(
            email=DEFAULT_USER_EMAIL,
            username=DEFAULT_USER_USERNAME,
            full_name=DEFAULT_USER_FULL_NAME,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    preview = _resolve_preview_role(x_developer_role)
    if preview and preview != user.role:
        # Return an in-memory copy so the preview role is never persisted onto
        # the shared demo user.
        return User(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            role=preview,
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str):
    """Dependency factory enforcing that the current user holds one of ``roles``.

    This is real server-side authorization (it runs before the endpoint body),
    but the identity it checks comes from the stub in :func:`get_current_user`,
    so it is only as trustworthy as the (currently absent) authentication layer.
    """

    allowed = set(roles)

    def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise ForbiddenError(
                "You do not have permission to perform this action.",
                code="insufficient_role",
                details={"required": sorted(allowed), "actual": user.role},
            )
        return user

    return dependency


LawyerUser = Annotated[User, Depends(require_role("lawyer"))]

__all__ = [
    "CurrentUser",
    "DbSession",
    "LawyerUser",
    "get_current_user",
    "require_role",
]
