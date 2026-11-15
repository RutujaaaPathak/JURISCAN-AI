from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token_claims
from app.models import COMPANY_ROLES, USER_ROLES, LawyerProfile, User

DbSession = Annotated[Session, Depends(get_db)]

# Explicit development/test convenience identity. It is only used when
# ALLOW_DEMO_USER is enabled and the environment is development or test; it is
# never available in production or staging.
DEFAULT_USER_EMAIL = "demo@juriscan.ai"
DEFAULT_USER_USERNAME = "demo-reviewer"
DEFAULT_USER_FULL_NAME = "Demo Reviewer"


def _demo_fallback_allowed() -> bool:
    return settings.allow_demo_user and settings.app_env in ("development", "test")


def _parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def _user_from_token(db: Session, token: str) -> User | None:
    claims = decode_access_token_claims(token, secret=settings.secret_key)
    if claims is None:
        return None
    user = db.get(User, claims.user_id)
    if user is None or not user.is_active:
        return None
    if user.token_version != claims.token_version:
        return None
    return user


def _ensure_default_user(db: Session) -> User:
    """Return (creating on first use) the development demo workspace user."""

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
    return user


def authenticate_token(db: Session, token: str | None) -> User | None:
    """Resolve a caller from a raw bearer token, for non-HTTP transports.

    WebSockets cannot set an ``Authorization`` header from the browser, so the
    token is delivered in the first message and validated here with the exact
    same signing scheme the HTTP layer uses. A supplied token must be valid; the
    explicit demo fallback is used solely when no token is presented and
    ALLOW_DEMO_USER is enabled outside production/staging.
    """

    if token:
        return _user_from_token(db, token)
    if _demo_fallback_allowed():
        return _ensure_default_user(db)
    return None


def _resolve_preview_role(requested: str | None) -> str | None:
    """Return the requested workspace role for a development preview request.

    This is intentionally NOT authentication: it performs no credential check
    and only takes effect when the explicit demo fallback is enabled outside
    production/staging. It exists so the single demo user can exercise
    role-specific endpoints in local development.
    """

    if not requested or not _demo_fallback_allowed():
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
        if user is None:
            # A supplied credential is never allowed to fall through to the demo
            # user, regardless of environment.
            raise UnauthorizedError(
                "Invalid or expired session.", code="invalid_token"
            )
        # A real session always wins over the development role preview, so an
        # authenticated request can never spoof its role via the header.
        return user

    if not _demo_fallback_allowed():
        raise UnauthorizedError("Authentication required.")

    user = _ensure_default_user(db)

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
            token_version=user.token_version,
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


def lawyer_verification_status(db: Session, user_id: int) -> str | None:
    """Return the lawyer's current verification status, or ``None``."""

    return db.scalar(
        select(LawyerProfile.verification_status).where(
            LawyerProfile.user_id == user_id
        )
    )


def ensure_verified_lawyer(db: Session, user: User) -> None:
    """Reject lawyers that have not completed verification.

    Callers use this for actions that expose confidential case resources. It is
    intentionally separate from :data:`LawyerUser`: unverified lawyers must
    still be able to manage their profile and submit verification documents.
    """

    if user.role != "lawyer":
        raise ForbiddenError(
            "You do not have permission to perform this action.",
            code="insufficient_role",
            details={"required": ["lawyer"], "actual": user.role},
        )
    status = lawyer_verification_status(db, user.id)
    if status != "VERIFIED":
        raise ForbiddenError(
            "Your lawyer account must be verified before accessing this case resource.",
            code="lawyer_verification_required",
            details={"verification_status": status},
        )


def require_verified_lawyer(db: DbSession, user: CurrentUser) -> User:
    ensure_verified_lawyer(db, user)
    return user


VerifiedLawyerUser = Annotated[User, Depends(require_verified_lawyer)]


def validate_session_token(db: Session, token: str | None, user_id: int) -> bool:
    """True when ``token`` is unexpired, active, and belongs to ``user_id``."""

    if not token:
        return False
    user = _user_from_token(db, token)
    return user is not None and user.id == user_id


def require_company_member(user: CurrentUser) -> User:
    """Require an authenticated company account with an active membership.

    Company membership is resolved from the session user, never from a request
    parameter, so one company can never read or mutate another company's team.
    """

    if user.role != "company":
        raise ForbiddenError(
            "This action is only available to company accounts.",
            code="insufficient_role",
            details={"required": ["company"], "actual": user.role},
        )
    if user.company_id is None or user.company_role not in COMPANY_ROLES:
        raise ForbiddenError(
            "This company workspace has no active membership.",
            code="company_membership_required",
        )
    return user


CompanyUser = Annotated[User, Depends(require_company_member)]


def require_company_admin(user: CompanyUser) -> User:
    if user.company_role != "COMPANY_ADMIN":
        raise ForbiddenError(
            "Only a company administrator can perform this action.",
            code="insufficient_company_role",
            details={"required": ["COMPANY_ADMIN"], "actual": user.company_role},
        )
    return user


CompanyAdmin = Annotated[User, Depends(require_company_admin)]

__all__ = [
    "AuthenticatedUser",
    "CompanyAdmin",
    "CompanyUser",
    "CurrentUser",
    "DbSession",
    "LawyerUser",
    "VerifiedLawyerUser",
    "authenticate_token",
    "ensure_verified_lawyer",
    "get_authenticated_user",
    "get_current_user",
    "lawyer_verification_status",
    "require_company_admin",
    "require_company_member",
    "require_role",
    "require_verified_lawyer",
    "validate_session_token",
]
