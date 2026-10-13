from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin

# Lifecycle of a lawyer's platform verification. ``VERIFIED`` is set by a human
# reviewer; no review tooling exists yet, so profiles start and normally remain
# ``UNVERIFIED`` and can only be moved to ``PENDING`` by the lawyer themselves.
LAWYER_VERIFICATION_STATUSES = ("UNVERIFIED", "PENDING", "VERIFIED", "REJECTED")


class LawyerProfile(Base, TimestampMixin):
    __tablename__ = "lawyer_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    bar_registration_number: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    jurisdiction: Mapped[str | None] = mapped_column(String(128), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    practice_areas: Mapped[list | None] = mapped_column(JSON, nullable=True)
    languages: Mapped[list | None] = mapped_column(JSON, nullable=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    consultation_modes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    fee_structure: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    availability: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(16), default="UNVERIFIED", nullable=False
    )
    # Free-text notes shown to the lawyer about their verification state. There
    # is no automated or admin review flow yet, so this stays empty unless set.
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('UNVERIFIED', 'PENDING', 'VERIFIED', 'REJECTED')",
            name="ck_lawyer_profiles_verification_status",
        ),
        CheckConstraint(
            "years_experience IS NULL OR years_experience >= 0",
            name="ck_lawyer_profiles_experience_non_negative",
        ),
    )

    def __repr__(self) -> str:
        return f"<LawyerProfile user_id={self.user_id} status={self.verification_status!r}>"
