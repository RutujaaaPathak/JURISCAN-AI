"""Company workspace models.

A company owns its documents and has members. Membership is intentionally stored
on ``User`` (one company per account) so authorization can be resolved from the
authenticated session without a join. Invitations store only a SHA-256 hash of
the single-use token; the raw token is returned once to the inviter and is never
persisted or logged.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

COMPANY_ROLES = ("COMPANY_ADMIN", "MANAGER", "MEMBER", "VIEWER")
INVITATION_STATUSES = ("PENDING", "ACCEPTED", "REVOKED", "EXPIRED")


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    members: Mapped[list["User"]] = relationship(
        back_populates="company",
        foreign_keys="User.company_id",
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="company",
        foreign_keys="Document.company_id",
    )
    invitations: Mapped[list["CompanyInvitation"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("name <> ''", name="ck_companies_name_not_empty"),
    )

    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name!r}>"


class CompanyInvitation(Base, TimestampMixin):
    __tablename__ = "company_invitations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    company_role: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), default="PENDING", server_default="PENDING", nullable=False
    )
    invited_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    company: Mapped["Company"] = relationship(back_populates="invitations")
    invited_by: Mapped["User | None"] = relationship(
        foreign_keys=[invited_by_user_id]
    )
    accepted_by: Mapped["User | None"] = relationship(
        foreign_keys=[accepted_by_user_id]
    )

    __table_args__ = (
        CheckConstraint("email <> ''", name="ck_company_invitations_email_not_empty"),
        CheckConstraint(
            "company_role IN ('COMPANY_ADMIN', 'MANAGER', 'MEMBER', 'VIEWER')",
            name="ck_company_invitations_role",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REVOKED', 'EXPIRED')",
            name="ck_company_invitations_status",
        ),
        Index("ix_company_invitations_company_status", "company_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<CompanyInvitation id={self.id} company_id={self.company_id} "
            f"email={self.email!r} status={self.status!r}>"
        )


__all__ = ["COMPANY_ROLES", "INVITATION_STATUSES", "Company", "CompanyInvitation"]
