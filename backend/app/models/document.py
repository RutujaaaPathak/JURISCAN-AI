from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

DOCUMENT_STATUSES = ("PENDING", "PROCESSING", "PROCESSED", "FAILED")


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Personal documents keep their uploader as owner. Company documents
    # outlive the employee who uploaded them, so deleting an account nulls this
    # reference instead of deleting the company's records.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    # Documents uploaded inside a company workspace belong to that company and
    # are readable by its members. Null for personal/lawyer documents. Company
    # documents cannot be silently detached by deleting the company.
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
    )
    # 0 is the explicit legacy plaintext marker; 1 requires the wrapped DEK.
    encryption_version: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default=text("0"), nullable=False
    )
    encryption_key_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dek_wrapped: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    # Retention controls are explicit deletion guards. A legal hold always wins;
    # retention_until blocks deletion until the configured date has passed.
    legal_hold: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("0"), nullable=False
    )
    retention_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User | None"] = relationship(back_populates="documents")
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
        CheckConstraint(
            "user_id IS NOT NULL OR company_id IS NOT NULL",
            name="ck_documents_owner_present",
        ),
        Index(
            "ix_documents_company_content_hash",
            "company_id",
            "content_hash",
            unique=True,
            postgresql_where=text("company_id IS NOT NULL AND content_hash IS NOT NULL"),
            sqlite_where=text("company_id IS NOT NULL AND content_hash IS NOT NULL"),
        ),
        Index(
            "ix_documents_user_personal_content_hash",
            "user_id",
            "content_hash",
            unique=True,
            postgresql_where=text("company_id IS NULL AND content_hash IS NOT NULL"),
            sqlite_where=text("company_id IS NULL AND content_hash IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename={self.filename!r} status={self.status!r}>"