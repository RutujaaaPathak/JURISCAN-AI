from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, Timestamped


class DocumentCreate(ORMModel):
    user_id: int
    title: str = Field(min_length=1, max_length=255)
    filename: str = Field(min_length=1, max_length=255)
    file_type: str = Field(min_length=1, max_length=16)
    mime_type: str | None = Field(default=None, max_length=128)


class DocumentRead(DocumentCreate, Timestamped):
    id: int
    status: str
    storage_path: str | None = None
    content_hash: str | None = None
    page_count: int | None = None
    word_count: int | None = None
    language: str | None = None
    extracted_at: datetime | None = None


class DocumentStatusUpdate(ORMModel):
    status: str = Field(pattern=r"^(PENDING|PROCESSING|PROCESSED|FAILED)$")


class ClauseRead(ORMModel, Timestamped):
    id: int
    document_id: int
    clause_number: int
    heading: str | None = None
    text: str
    start_offset: int | None = None
    end_offset: int | None = None
    page_number: int | None = None
    clause_type: str | None = None
    risk_level: str | None = None


class RiskFindingRead(ORMModel, Timestamped):
    id: int
    analysis_id: int
    clause_id: int | None = None
    rule_code: str | None = None
    severity: str
    title: str
    description: str
    recommendation: str | None = None
    citation: str | None = None
    clause_number: int | None = None
    clause_heading: str | None = None
    clause_page: int | None = None


class AnalysisRead(ORMModel, Timestamped):
    id: int
    document_id: int
    model_name: str
    status: str
    risk_score: float | None = None
    safety_score: float | None = None
    summary: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AnalysisDetail(AnalysisRead):
    findings: list[RiskFindingRead] = Field(default_factory=list)


class DocumentSummary(ORMModel):
    id: int
    title: str
    filename: str
    file_type: str
    status: str
    page_count: int | None = None
    word_count: int | None = None
    language: str | None = None
    extracted_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    analysis_id: int | None = None
    analysis_status: str | None = None
    model_name: str | None = None
    risk_score: float | None = None
    risk_level: str | None = None
    safety_score: float | None = None
    finding_count: int = 0
    high_risk_count: int = 0


class DocumentPage(ORMModel):
    """Character range of a single source page within the extracted text."""

    page_number: int
    start_offset: int
    end_offset: int


class DocumentDetail(DocumentSummary):
    # Full extracted text (private storage paths are never included here).
    text_content: str | None = None
    # Page boundaries within ``text_content``; empty for DOCX/TXT, which have no
    # reliable page information.
    pages: list[DocumentPage] = Field(default_factory=list)
    clauses: list[ClauseRead] = Field(default_factory=list)
    analysis: AnalysisDetail | None = None


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary]
    total: int


class DeleteAllResult(BaseModel):
    deleted: int


class CategoryCount(BaseModel):
    category: str
    count: int


class TrendPoint(BaseModel):
    date: str
    count: int


class OverviewStats(BaseModel):
    total_documents: int
    processed: int
    processing: int
    failed: int
    avg_risk_score: float
    high_risk_findings: int
    risk_distribution: dict[str, int]
    category_counts: list[CategoryCount]
    upload_trend: list[TrendPoint]
