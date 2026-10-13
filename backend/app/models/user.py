from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

# Workspace roles a user can hold. This is a plain string column rather than a
# database enum so the SQLite test database and PostgreSQL share one definition.
USER_ROLES = ("individual", "company", "lawyer", "admin")


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
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Workspace role. Authorization is enforced server-side against this value,
    # but note that no authentication exists yet: every request resolves to the
    # single default workspace user (see app/api/deps.py). This column is the
    # foundation the auth layer will populate later.
    role: Mapped[str] = mapped_column(
        String(16), default="individual", server_default="individual", nullable=False
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("email <> ''", name="ck_users_email_not_empty"),
        CheckConstraint("username <> ''", name="ck_users_username_not_empty"),
        CheckConstraint(
            "role IN ('individual', 'company', 'lawyer', 'admin')",
            name="ck_users_role",
        ),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"