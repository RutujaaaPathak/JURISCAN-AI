from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

DOCUMENT_STATUSES = ("PENDING", "PROCESSING", "PROCESSED", "FAILED")


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Documents uploaded inside a company workspace belong to that company and
    # are readable by its members. Null for personal/lawyer documents.
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default="PENDING", nullable=False
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_spans: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    ocr_quality: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    quality_warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="documents")
    company: Mapped["Company | None"] = relationship(
        back_populates="documents", foreign_keys=[company_id]
    )
    clauses: Mapped[list["Clause"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ('PENDING', 'PROCESSING', 'PROCESSED', 'FAILED')",
            name="ck_documents_status",
        ),
        CheckConstraint(
            "file_type IN ('pdf', 'docx', 'txt', 'other')",
            name="ck_documents_file_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename={self.filename!r} status={self.status!r}>"