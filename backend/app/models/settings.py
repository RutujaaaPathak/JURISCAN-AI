from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin

# Analysis preferences a user can persist from the Settings page.
SEVERITY_LEVELS = ("low", "medium", "high", "critical")
ANALYSIS_MODELS = ("rules", "heuristic", "legal-bert")


class UserSettings(Base, TimestampMixin):
    """Per-user workspace preferences.

    Account identity fields (email, full name) live on :class:`User`; this table
    only holds the preferences a user can tune. One row per user, enforced by the
    unique ``user_id`` index, so an account can never read another's settings.
    """

    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    # Free-text primary jurisdiction. Empty means "not configured" — the UI must
    # show an empty state rather than invent a location.
    jurisdiction: Mapped[str | None] = mapped_column(String(128), nullable=True)
    min_severity: Mapped[str] = mapped_column(
        String(16), default="medium", server_default="medium", nullable=False
    )
    analysis_model: Mapped[str] = mapped_column(
        String(32), default="rules", server_default="rules", nullable=False
    )
    auto_analyze: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Notification toggles. There is no outbound email/SMS sender yet, so these
    # only record intent; the UI must not claim delivery happens.
    notify_email_digest: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    notify_high_risk: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_weekly_report: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "min_severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_user_settings_min_severity",
        ),
        CheckConstraint(
            "analysis_model IN ('rules', 'heuristic', 'legal-bert')",
            name="ck_user_settings_analysis_model",
        ),
    )

    def __repr__(self) -> str:
        return f"<UserSettings user_id={self.user_id}>"
