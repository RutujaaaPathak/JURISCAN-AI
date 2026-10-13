from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

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

    # Hierarchy and structural metadata
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("clauses.id", ondelete="SET NULL"), index=True, nullable=True
    )

    document: Mapped["Document"] = relationship(back_populates="clauses")
    risk_findings: Mapped[list["RiskFinding"]] = relationship(
        back_populates="clause"
    )

    parent: Mapped["Clause | None"] = relationship(
        "Clause",
        remote_side=[id],
        back_populates="children",
    )
    children: Mapped[list["Clause"]] = relationship(
        "Clause",
        back_populates="parent",
    )

    __table_args__ = (
        UniqueConstraint("document_id", "clause_number", name="uq_clauses_document_number"),
        CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_clauses_risk_level",
        ),
        CheckConstraint("level >= 1", name="ck_clauses_level_positive"),
        Index("ix_clauses_document_risk", "document_id", "risk_level"),
        Index("ix_clauses_document_parent", "document_id", "parent_id"),
    )

    @validates("parent_id")
    def validate_parent_id(self, key: str, value: int | None) -> int | None:
        if value is not None and self.id is not None and value == self.id:
            raise ValueError("A clause cannot be its own parent.")
        return value

    @validates("parent")
    def validate_parent(self, key: str, value: "Clause | None") -> "Clause | None":
        if value is not None:
            if self.id is not None and value.id is not None and value.id == self.id:
                raise ValueError("A clause cannot be its own parent.")
            if self.document_id is not None and value.document_id is not None:
                if self.document_id != value.document_id:
                    raise ValueError("Parent clause must belong to the same document.")
        return value

    def __repr__(self) -> str:
        return f"<Clause id={self.id} document_id={self.document_id} number={self.clause_number}>"


@event.listens_for(Clause, "before_insert")
@event.listens_for(Clause, "before_update")
def _validate_clause_hierarchy(mapper, connection, target: Clause) -> None:
    if target.parent_id is not None:
        if target.id is not None and target.parent_id == target.id:
            raise ValueError("A clause cannot be its own parent.")
        if target.parent is not None:
            if target.parent.document_id != target.document_id:
                raise ValueError("Parent clause must belong to the same document.")
        else:
            parent_doc = connection.scalar(
                select(Clause.document_id).where(Clause.id == target.parent_id)
            )
            if parent_doc is not None and parent_doc != target.document_id:
                raise ValueError("Parent clause must belong to the same document.")