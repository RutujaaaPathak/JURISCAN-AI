from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models import USER_ROLES, User

DbSession = Annotated[Session, Depends(get_db)]

# Development/test fallback only. When no bearer token is supplied outside
# production, requests resolve to this single default workspace user so the
# app remains usable (and the existing test-suite keeps working) before every
# client has signed in. Production requires a valid token instead.
DEFAULT_USER_EMAIL = "demo@juriscan.ai"
DEFAULT_USER_USERNAME = "demo-reviewer"
DEFAULT_USER_FULL_NAME = "Demo Reviewer"


def _parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def _user_from_token(db: Session, token: str) -> User | None:
    user_id = decode_access_token(token, secret=settings.secret_key)
    if user_id is None:
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


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
    authorization: Annotated[str | None, Header()] = None,
    x_developer_role: Annotated[str | None, Header(alias="X-Developer-Role")] = None,
) -> User:
    token = _parse_bearer_token(authorization)
    if token:
        user = _user_from_token(db, token)
        if user is not None:
            # A real session always wins over the development role preview, so an
            # authenticated request can never spoof its role via the header.
            return user
        if settings.app_env == "production":
            raise UnauthorizedError("Invalid or expired session.", code="invalid_token")
    elif settings.app_env == "production":
        raise UnauthorizedError("Authentication required.")

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


def get_authenticated_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Strict authentication: a valid bearer token is mandatory.

    Unlike :func:`get_current_user` there is no demo fallback, so this is what
    session-sensitive endpoints use to prove the caller's identity.
    """

    token = _parse_bearer_token(authorization)
    if not token:
        raise UnauthorizedError("Authentication required.")
    user = _user_from_token(db, token)
    if user is None:
        raise UnauthorizedError("Invalid or expired session.", code="invalid_token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

AuthenticatedUser = Annotated[User, Depends(get_authenticated_user)]


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
    "AuthenticatedUser",
    "CurrentUser",
    "DbSession",
    "LawyerUser",
    "get_authenticated_user",
    "get_current_user",
    "require_role",
]
