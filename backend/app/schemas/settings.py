"""User profile / workspace settings schemas.

The payload is intentionally flat: it combines account fields that live on
``users`` (full name, company organisation) with per-user preferences stored in
``user_settings``. Email is deliberately absent from the update schema — it is
the account identity and can only change through a dedicated, verified flow, not
a free-text settings form.
"""

from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field

from app.schemas.common import ORMModel

SeverityLevel = Literal["low", "medium", "high", "critical"]
AnalysisModel = Literal["rules", "heuristic", "legal-bert"]


class UserSettingsRead(ORMModel):
    email: EmailStr
    full_name: str | None
    role: str
    organization_name: str | None
    jurisdiction: str | None
    min_severity: str
    analysis_model: str
    auto_analyze: bool
    notify_email_digest: bool
    notify_high_risk: bool
    notify_weekly_report: bool
    updated_at: datetime


class UserSettingsUpdate(ORMModel):
    # Only the fields a user is allowed to change. ``email`` is intentionally
    # omitted. All fields are optional so a section can be saved on its own.
    full_name: str | None = Field(default=None, max_length=255)
    organization_name: str | None = Field(default=None, max_length=255)
    jurisdiction: str | None = Field(default=None, max_length=128)
    min_severity: SeverityLevel | None = None
    analysis_model: AnalysisModel | None = None
    auto_analyze: bool | None = None
    notify_email_digest: bool | None = None
    notify_high_risk: bool | None = None
    notify_weekly_report: bool | None = None


__all__ = ["AnalysisModel", "SeverityLevel", "UserSettingsRead", "UserSettingsUpdate"]
