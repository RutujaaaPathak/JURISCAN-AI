"""Company team management and invitation acceptance."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CompanyAdmin, CompanyUser, DbSession
from app.config import settings
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationFailed,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.models import (
    COMPANY_ROLES,
    Company,
    CompanyInvitation,
    User,
)
from app.schemas.auth import AuthUser, TokenResponse
from app.schemas.company import (
    CompanyProfile,
    CompanyRoleUpdate,
    InvitationAcceptRequest,
    InvitationCreate,
    InvitationCreateResponse,
    InvitationListResponse,
    InvitationPreview,
    InvitationRead,
    TeamMemberListResponse,
    TeamMemberRead,
    TeamOverview,
)
from app.services.company import (
    generate_invitation_token,
    hash_invitation_token,
    invitation_is_expired,
    normalize_email,
)
from app.services.users import unique_username

router = APIRouter(prefix="/company", tags=["company"])


def _company_or_404(db: DbSession, company_id: int) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise NotFoundError(
            "The company workspace was not found.",
            code="company_not_found",
            details={"company_id": company_id},
        )
    return company


def _member_payload(user: User, *, current_user_id: int) -> dict:
    return {
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "company_role": user.company_role,
        "account_status": "ACTIVE" if user.is_active else "INACTIVE",
        "joined_at": user.created_at,
        "is_self": user.id == current_user_id,
    }


def _invitation_status(invitation: CompanyInvitation) -> str:
    if invitation.status == "PENDING" and invitation_is_expired(invitation):
        return "EXPIRED"
    return invitation.status


def _invitation_payload(invitation: CompanyInvitation) -> dict:
    return {
        "id": invitation.id,
        "email": invitation.email,
        "company_role": invitation.company_role,
        "status": _invitation_status(invitation),
        "invited_by_name": (
            invitation.invited_by.full_name or invitation.invited_by.email
            if invitation.invited_by
            else None
        ),
        "created_at": invitation.created_at,
        "expires_at": invitation.expires_at,
        "accepted_at": invitation.accepted_at,
        "is_expired": invitation_is_expired(invitation),
    }


def _members(db: DbSession, company_id: int) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.company_id == company_id, User.company_role.is_not(None))
            .order_by(User.created_at.asc(), User.id.asc())
        ).all()
    )


def _count_active_admins(
    db: DbSession, company_id: int, *, exclude_user_id: int | None = None
) -> int:
    stmt = select(func.count(User.id)).where(
        User.company_id == company_id,
        User.company_role == "COMPANY_ADMIN",
        User.is_active.is_(True),
    )
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    return int(db.scalar(stmt) or 0)


def _pending_invitations(db: DbSession, company_id: int) -> list[CompanyInvitation]:
    return list(
        db.scalars(
            select(CompanyInvitation)
            .options(selectinload(CompanyInvitation.invited_by))
            .where(
                CompanyInvitation.company_id == company_id,
                CompanyInvitation.status == "PENDING",
            )
            .order_by(CompanyInvitation.created_at.desc())
        ).all()
    )


@router.get("/team/overview", response_model=TeamOverview)
def team_overview(db: DbSession, user: CompanyUser) -> dict:
    assert user.company_id is not None
    company = _company_or_404(db, user.company_id)
    members = _members(db, user.company_id)
    pending = [
        invitation
        for invitation in _pending_invitations(db, user.company_id)
        if not invitation_is_expired(invitation)
    ]
    role_counts = {role: 0 for role in COMPANY_ROLES}
    for member in members:
        if member.company_role in role_counts:
            role_counts[member.company_role] += 1
    return {
        "company": CompanyProfile(id=company.id, name=company.name),
        "total_members": len(members),
        "active_members": sum(1 for member in members if member.is_active),
        "pending_invitations": len(pending),
        "role_counts": role_counts,
    }


@router.get("/team", response_model=TeamMemberListResponse)
def list_team_members(db: DbSession, user: CompanyUser) -> dict:
    assert user.company_id is not None
    items = [
        _member_payload(member, current_user_id=user.id)
        for member in _members(db, user.company_id)
    ]
    return {"items": items, "total": len(items)}


@router.patch(
    "/team/members/{member_id}/role", response_model=TeamMemberRead
)
def update_member_role(
    db: DbSession,
    user: CompanyAdmin,
    member_id: int,
    payload: CompanyRoleUpdate,
) -> dict:
    assert user.company_id is not None
    member = db.scalar(
        select(User).where(
            User.id == member_id,
            User.company_id == user.company_id,
            User.company_role.is_not(None),
        )
    )
    if member is None:
        raise NotFoundError(
            f"Team member {member_id} was not found.",
            code="team_member_not_found",
            details={"member_id": member_id},
        )

    if member.company_role == payload.company_role:
        return _member_payload(member, current_user_id=user.id)

    if (
        member.company_role == "COMPANY_ADMIN"
        and payload.company_role != "COMPANY_ADMIN"
        and _count_active_admins(
            db, user.company_id, exclude_user_id=member.id
        )
        == 0
    ):
        raise ConflictError(
            "A company must keep at least one active administrator.",
            code="last_company_admin",
            details={"member_id": member.id},
        )

    member.company_role = payload.company_role
    db.commit()
    db.refresh(member)
    return _member_payload(member, current_user_id=user.id)


@router.delete("/team/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_team_member(db: DbSession, user: CompanyAdmin, member_id: int) -> Response:
    assert user.company_id is not None
    member = db.scalar(
        select(User).where(
            User.id == member_id,
            User.company_id == user.company_id,
            User.company_role.is_not(None),
        )
    )
    if member is None:
        raise NotFoundError(
            f"Team member {member_id} was not found.",
            code="team_member_not_found",
            details={"member_id": member_id},
        )

    if member.company_role == "COMPANY_ADMIN" and _count_active_admins(
        db, user.company_id, exclude_user_id=member.id
    ) == 0:
        raise ConflictError(
            "A company must keep at least one active administrator.",
            code="last_company_admin",
            details={"member_id": member.id},
        )

    member.company_id = None
    member.company_role = None
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/team/invitations", response_model=InvitationListResponse)
def list_invitations(db: DbSession, user: CompanyUser) -> dict:
    assert user.company_id is not None
    invitations = list(
        db.scalars(
            select(CompanyInvitation)
            .options(selectinload(CompanyInvitation.invited_by))
            .where(CompanyInvitation.company_id == user.company_id)
            .order_by(CompanyInvitation.created_at.desc())
        ).all()
    )
    items = [_invitation_payload(invitation) for invitation in invitations]
    return {"items": items, "total": len(items)}


@router.post(
    "/team/invitations",
    response_model=InvitationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    db: DbSession, user: CompanyAdmin, payload: InvitationCreate
) -> dict:
    assert user.company_id is not None
    email = normalize_email(payload.email)

    existing_user = db.scalar(
        select(User).where(func.lower(User.email) == email)
    )
    if existing_user is not None:
        if existing_user.company_id == user.company_id:
            raise ConflictError(
                "This person is already a member of your company.",
                code="already_company_member",
            )
        if existing_user.company_id is not None:
            raise ConflictError(
                "This person already belongs to another company.",
                code="already_in_company",
            )

    existing_pending = db.scalar(
        select(CompanyInvitation.id).where(
            CompanyInvitation.company_id == user.company_id,
            func.lower(CompanyInvitation.email) == email,
            CompanyInvitation.status == "PENDING",
        )
    )
    if existing_pending is not None:
        raise ConflictError(
            "A pending invitation already exists for this email.",
            code="invitation_pending",
        )

    token = generate_invitation_token()
    now = datetime.now(timezone.utc)
    invitation = CompanyInvitation(
        company_id=user.company_id,
        email=email,
        company_role=payload.company_role,
        token_hash=hash_invitation_token(token),
        status="PENDING",
        invited_by_user_id=user.id,
        expires_at=now + timedelta(hours=settings.company_invitation_ttl_hours),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    db.refresh(invitation, attribute_names=["invited_by"])

    development = settings.app_env != "production"
    accept_url = (
        f"{settings.frontend_origin.rstrip('/')}/invite/{token}"
        if development
        else None
    )
    return {
        "invitation": _invitation_payload(invitation),
        "email_sent": False,
        "development_invitation_token": token if development else None,
        "development_accept_url": accept_url,
    }


@router.post(
    "/team/invitations/{invitation_id}/revoke", response_model=InvitationRead
)
def revoke_invitation(
    db: DbSession, user: CompanyAdmin, invitation_id: int
) -> dict:
    assert user.company_id is not None
    invitation = db.scalar(
        select(CompanyInvitation)
        .options(selectinload(CompanyInvitation.invited_by))
        .where(
            CompanyInvitation.id == invitation_id,
            CompanyInvitation.company_id == user.company_id,
        )
    )
    if invitation is None:
        raise NotFoundError(
            f"Invitation {invitation_id} was not found.",
            code="invitation_not_found",
            details={"invitation_id": invitation_id},
        )
    if invitation.status != "PENDING":
        raise ConflictError(
            "Only a pending invitation can be revoked.",
            code="invitation_not_pending",
            details={"status": _invitation_status(invitation)},
        )
    if invitation_is_expired(invitation):
        invitation.status = "EXPIRED"
        db.commit()
        db.refresh(invitation)
        raise ConflictError(
            "This invitation has already expired.",
            code="invitation_expired",
        )

    invitation.status = "REVOKED"
    db.commit()
    db.refresh(invitation)
    return _invitation_payload(invitation)


def _find_invitation(
    db: DbSession, token: str, *, for_update: bool = False
) -> CompanyInvitation:
    stmt = (
        select(CompanyInvitation)
        .options(selectinload(CompanyInvitation.company))
        .where(CompanyInvitation.token_hash == hash_invitation_token(token))
    )
    if for_update:
        stmt = stmt.with_for_update()
    invitation = db.scalar(stmt)
    if invitation is None:
        raise ValidationFailed(
            "This invitation link is not valid.",
            code="invalid_invitation",
        )
    return invitation


@router.get("/invitations/preview", response_model=InvitationPreview)
def preview_invitation(
    db: DbSession, token: str = Query(min_length=20, max_length=256)
) -> dict:
    invitation = _find_invitation(db, token)
    email = normalize_email(invitation.email)
    account_exists = (
        db.scalar(select(User.id).where(func.lower(User.email) == email))
        is not None
    )
    return {
        "company_name": invitation.company.name,
        "email": email,
        "company_role": invitation.company_role,
        "expires_at": invitation.expires_at,
        "status": _invitation_status(invitation),
        "is_expired": invitation_is_expired(invitation),
        "account_exists": account_exists,
    }


@router.post("/invitations/accept", response_model=TokenResponse)
def accept_invitation(db: DbSession, payload: InvitationAcceptRequest) -> dict:
    invitation = _find_invitation(db, payload.token, for_update=True)
    if invitation.status == "ACCEPTED":
        raise ConflictError(
            "This invitation has already been accepted.",
            code="invitation_used",
        )
    if invitation.status == "REVOKED":
        raise ConflictError(
            "This invitation was revoked.", code="invitation_revoked"
        )
    if invitation.status == "EXPIRED" or invitation_is_expired(invitation):
        if invitation.status == "PENDING":
            invitation.status = "EXPIRED"
            db.commit()
        raise ValidationFailed(
            "This invitation has expired.", code="invitation_expired"
        )

    email = normalize_email(invitation.email)
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is not None:
        if not user.is_active:
            raise ForbiddenError(
                "This account is disabled.", code="account_disabled"
            )
        if user.hashed_password is None or not verify_password(
            payload.password, user.hashed_password
        ):
            raise UnauthorizedError(
                "Enter the password for the existing account with this email.",
                code="invalid_credentials",
            )
        if user.company_id is not None:
            if user.company_id == invitation.company_id:
                raise ConflictError(
                    "This account is already a member of this company.",
                    code="already_company_member",
                )
            raise ConflictError(
                "This account already belongs to another company.",
                code="already_in_company",
            )
        if user.role not in ("individual", "company"):
            raise ConflictError(
                "This account type cannot join a company workspace.",
                code="incompatible_account",
                details={"role": user.role},
            )
        user.role = "company"
        user.company_id = invitation.company_id
        user.company_role = invitation.company_role
        user.organization_name = user.organization_name or invitation.company.name
    else:
        full_name = (payload.full_name or "").strip()
        if not full_name:
            raise ValidationFailed(
                "Full name is required to create an account.",
                code="full_name_required",
            )
        user = User(
            email=email,
            username=unique_username(db, email),
            full_name=full_name,
            hashed_password=hash_password(payload.password),
            organization_name=invitation.company.name,
            role="company",
            company_id=invitation.company_id,
            company_role=invitation.company_role,
            is_active=True,
        )
        db.add(user)
        db.flush()

    invitation.status = "ACCEPTED"
    invitation.accepted_at = datetime.now(timezone.utc)
    invitation.accepted_by_user_id = user.id
    db.commit()
    db.refresh(user)

    ttl = settings.access_token_ttl_seconds
    return {
        "access_token": create_access_token(
            user.id, secret=settings.secret_key, ttl_seconds=ttl
        ),
        "token_type": "bearer",
        "expires_in": ttl,
        "user": AuthUser.model_validate(user),
    }


__all__ = ["router"]
