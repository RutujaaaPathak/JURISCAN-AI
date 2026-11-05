from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

# Workspace roles a user can hold. This is a plain string column rather than a
# database enum so the SQLite test database and PostgreSQL share one definition.
USER_ROLES = ("individual", "company", "lawyer", "admin")

# Role inside a company team. ``company_role`` is null for non-company accounts
# and is always enforced server-side; it is independent of ``role`` above.
COMPANY_ROLES = ("COMPANY_ADMIN", "MANAGER", "MEMBER", "VIEWER")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Company accounts store their organisation name here; null for other roles.
    organization_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Workspace role. Authorization is enforced server-side against this value.
    # It is set from the authenticated account (see app/api/deps.py); outside
    # production an unauthenticated request still falls back to a shared demo
    # user for backwards compatibility.
    role: Mapped[str] = mapped_column(
        String(16), default="individual", server_default="individual", nullable=False
    )

    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    company_role: Mapped[str | None] = mapped_column(String(16), nullable=True)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    company: Mapped["Company | None"] = relationship(
        back_populates="members", foreign_keys=[company_id]
    )

    __table_args__ = (
        CheckConstraint("email <> ''", name="ck_users_email_not_empty"),
        CheckConstraint("username <> ''", name="ck_users_username_not_empty"),
        CheckConstraint(
            "role IN ('individual', 'company', 'lawyer', 'admin')",
            name="ck_users_role",
        ),
        CheckConstraint(
            "company_role IS NULL OR company_role IN "
            "('COMPANY_ADMIN', 'MANAGER', 'MEMBER', 'VIEWER')",
            name="ck_users_company_role",
        ),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"