from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


class Clause(Base, TimestampMixin):
    __tablename__ = "clauses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    clause_number: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clause_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)

    document: Mapped["Document"] = relationship(back_populates="clauses")
    risk_findings: Mapped[list["RiskFinding"]] = relationship(
        back_populates="clause"
    )

    __table_args__ = (
        UniqueConstraint("document_id", "clause_number", name="uq_clauses_document_number"),
        CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_clauses_risk_level",
        ),
        Index("ix_clauses_document_risk", "document_id", "risk_level"),
    )

    def __repr__(self) -> str:
        return f"<Clause id={self.id} document_id={self.document_id} number={self.clause_number}>"