from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


class RiskFinding(Base, TimestampMixin):
    __tablename__ = "risk_findings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    clause_id: Mapped[int | None] = mapped_column(
        ForeignKey("clauses.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    rule_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)

    analysis: Mapped["Analysis"] = relationship(back_populates="risk_findings")
    clause: Mapped["Clause"] = relationship(back_populates="risk_findings")

    __table_args__ = (
        CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_risk_findings_severity",
        ),
        Index("ix_risk_findings_analysis_severity", "analysis_id", "severity"),
    )

    def __repr__(self) -> str:
        return f"<RiskFinding id={self.id} analysis_id={self.analysis_id} severity={self.severity!r}>"