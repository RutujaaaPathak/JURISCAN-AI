"""Schemas for the company team and audit-report workspace."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel
from app.schemas.documents import RiskFindingRead

CompanyRole = Literal["COMPANY_ADMIN", "MANAGER", "MEMBER", "VIEWER"]
InvitationStatus = Literal["PENDING", "ACCEPTED", "REVOKED", "EXPIRED"]


class CompanyProfile(BaseModel):
    id: int
    name: str


class TeamMemberRead(BaseModel):
    user_id: int
    full_name: str | None
    email: EmailStr
    company_role: CompanyRole
    account_status: Literal["ACTIVE", "INACTIVE"]
    joined_at: datetime
    is_self: bool


class TeamMemberListResponse(BaseModel):
    items: list[TeamMemberRead]
    total: int


class TeamOverview(BaseModel):
    company: CompanyProfile
    total_members: int
    active_members: int
    pending_invitations: int
    role_counts: dict[str, int]


class CompanyRoleUpdate(BaseModel):
    company_role: CompanyRole


class InvitationCreate(BaseModel):
    email: EmailStr
    company_role: CompanyRole


class InvitationRead(BaseModel):
    id: int
    email: EmailStr
    company_role: CompanyRole
    status: InvitationStatus
    invited_by_name: str | None
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    is_expired: bool


class InvitationListResponse(BaseModel):
    items: list[InvitationRead]
    total: int


class InvitationCreateResponse(BaseModel):
    invitation: InvitationRead
    email_sent: bool = False
    # Only populated outside production, where there is no email transport.
    # The raw token is returned once and only its SHA-256 hash is stored.
    development_invitation_token: str | None = None
    development_accept_url: str | None = None


class InvitationPreview(BaseModel):
    company_name: str
    email: EmailStr
    company_role: CompanyRole
    expires_at: datetime
    status: InvitationStatus
    is_expired: bool
    account_exists: bool


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    full_name: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class AuditReportSummary(BaseModel):
    document_id: int
    document_title: str
    filename: str
    file_type: str
    analysis_id: int | None = None
    model_name: str | None = None
    analysis_status: str | None = None
    report_status: Literal["READY", "PENDING", "FAILED", "NOT_GENERATED"]
    audit_date: datetime | None = None
    risk_score: float | None = None
    risk_level: str | None = None
    safety_score: float | None = None
    finding_count: int = 0
    high_risk_count: int = 0
    error_message: str | None = None


class AuditReportListResponse(BaseModel):
    items: list[AuditReportSummary]
    total: int


class AuditReportDetail(AuditReportSummary):
    analysis_summary: str | None = None
    clause_count: int = 0
    findings: list[RiskFindingRead] = Field(default_factory=list)


class AuditActivity(BaseModel):
    document_id: int
    document_title: str
    event: str
    report_status: str
    risk_level: str | None = None
    risk_score: float | None = None
    occurred_at: datetime


class AuditReportOverview(BaseModel):
    total_reports: int
    ready_reports: int
    failed_reports: int
    high_risk_reports: int
    medium_risk_reports: int = 0
    low_risk_reports: int = 0
    requiring_attention: int
    avg_risk_score: float
    recent_activity: list[AuditActivity]


__all__ = [
    "AuditActivity",
    "AuditReportDetail",
    "AuditReportListResponse",
    "AuditReportOverview",
    "AuditReportSummary",
    "CompanyProfile",
    "CompanyRole",
    "CompanyRoleUpdate",
    "InvitationAcceptRequest",
    "InvitationCreate",
    "InvitationCreateResponse",
    "InvitationListResponse",
    "InvitationPreview",
    "InvitationRead",
    "InvitationStatus",
    "TeamMemberListResponse",
    "TeamMemberRead",
    "TeamOverview",
]
