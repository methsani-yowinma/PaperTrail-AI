"""Public API request/response schemas (the contract consumed by the Next.js frontend)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.records import (
    AssessmentStatus,
    Directness,
    EvidenceStrength,
    EvidenceType,
    InvestigationStatus,
    PassageRelation,
    ProcessingStatus,
    Verdict,
)

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# ---- system --------------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class SystemStatus(BaseModel):
    app_env: str
    auth_mode: Literal["local", "supabase"]
    database_backend: Literal["sqlite", "postgres"]
    storage_backend: Literal["local", "supabase"]
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    assessment_configured: bool
    gemini_model: str | None
    methodology_version: str
    prompt_version: str
    max_upload_size_mb: int
    max_pdf_pages: int
    database_ok: bool


class ModelCheckResponse(BaseModel):
    ok: bool
    model: str | None
    detail: dict[str, Any] | None = None
    error: str | None = None


class CurrentUser(BaseModel):
    id: str
    email: str | None = None
    auth_mode: Literal["local", "supabase"]


# ---- documents -----------------------------------------------------------------------------
class DocumentOut(BaseModel):
    id: str
    original_filename: str
    title: str | None
    authors: list[str]
    publication_year: int | None
    doi: str | None
    source_url: str | None
    file_size_bytes: int
    page_count: int | None
    page_labels: list[str] | None
    processing_status: ProcessingStatus
    processing_error: str | None
    extraction_warnings: list[str]
    metadata_sources: dict[str, str]
    embedding_model: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=500)
    authors: list[str] | None = Field(default=None, max_length=50)
    publication_year: int | None = Field(default=None, ge=1400, le=2200)
    doi: str | None = Field(default=None, max_length=200, pattern=r"^10\.\d{4,9}/\S+$")
    source_url: str | None = Field(default=None, max_length=1000, pattern=r"^https?://\S+$")

    @field_validator("authors")
    @classmethod
    def _clean_authors(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [v.strip()[:200] for v in value if v and v.strip()]
        return cleaned

    @field_validator("title")
    @classmethod
    def _clean_title(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ChunkOut(BaseModel):
    id: str
    chunk_index: int
    page_start: int
    page_end: int
    page_label: str | None
    section_title: str | None
    content: str
    token_count: int


# ---- investigations ------------------------------------------------------------------------
class InvestigationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_k: int = Field(default=8, ge=3, le=20)


class InvestigationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    claim_text: str = Field(min_length=5, max_length=2000)
    research_context: str | None = Field(default=None, max_length=4000)
    document_ids: list[str] = Field(min_length=1, max_length=50)
    settings: InvestigationSettings = Field(default_factory=InvestigationSettings)

    @field_validator("claim_text")
    @classmethod
    def _strip_claim(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 5:
            raise ValueError("The claim must contain at least 5 characters.")
        return value

    @field_validator("document_ids")
    @classmethod
    def _unique_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class DocumentRef(BaseModel):
    id: str
    title: str | None
    original_filename: str
    authors: list[str]
    publication_year: int | None
    processing_status: ProcessingStatus


class AssessmentSummary(BaseModel):
    id: str
    status: AssessmentStatus
    verdict: Verdict | None
    created_at: datetime
    error_message: str | None


class InvestigationOut(BaseModel):
    id: str
    title: str
    claim_text: str
    research_context: str | None
    status: InvestigationStatus
    overall_verdict: Verdict | None
    methodology_version: str
    settings: dict[str, Any]
    last_error: str | None
    documents: list[DocumentRef]
    missing_document_count: int = 0
    latest_assessment: AssessmentSummary | None = None
    created_at: datetime
    updated_at: datetime


# ---- evidence & assessments ----------------------------------------------------------------
class RetrievalInfo(BaseModel):
    method: str
    rank: int
    keyword_rank: int | None
    semantic_rank: int | None
    fused_score: float = Field(description="Reciprocal-rank-fusion score. Orders passages; not a probability.")
    semantic_similarity: float | None = Field(description="Cosine similarity of embeddings. Not evidence of truth.")


class CitationOut(BaseModel):
    valid: bool
    issues: list[str]
    document_id: str | None
    chunk_id: str | None
    document_title: str | None
    original_filename: str | None
    authors: list[str]
    publication_year: int | None
    doi: str | None
    page_start: int | None
    page_end: int | None
    page_label: str | None
    section_title: str | None
    passage_text: str | None = Field(description="Exact stored passage text (never model-generated).")
    excerpt_start: int | None
    excerpt_end: int | None
    excerpt_verified: bool
    excerpt_text: str | None = Field(description="Slice of passage_text at the verified offsets, if any.")
    reference: str | None = Field(description="Human-readable citation built from stored metadata.")


class EvidenceOut(BaseModel):
    id: str
    label: str
    relation: PassageRelation
    directness: Directness | None
    evidence_strength: EvidenceStrength | None
    evidence_type: EvidenceType | None
    model_confidence: float | None = Field(description="Model-reported, uncalibrated.")
    rationale: str | None
    limitations: list[str]
    retrieval: RetrievalInfo
    citation: CitationOut


class AssessmentOut(BaseModel):
    id: str
    investigation_id: str
    status: AssessmentStatus
    verdict: Verdict | None
    explanation: str | None
    explanation_source: str | None
    limitations: list[str]
    reasons: list[str]
    evidence_summary: dict[str, Any]
    model_identifier: str | None
    prompt_version: str | None
    methodology_version: str | None
    retrieval_configuration: dict[str, Any]
    metadata: dict[str, Any]
    error_message: str | None
    created_at: datetime
    evidence: list[EvidenceOut]


class VerifyResponse(BaseModel):
    investigation: InvestigationOut
    assessment: AssessmentOut


# ---- reports -------------------------------------------------------------------------------
class ReportListItem(BaseModel):
    id: str
    investigation_id: str
    investigation_title: str
    claim_text: str
    verdict: Verdict | None
    created_at: datetime


class ReportSource(BaseModel):
    document_id: str
    title: str | None
    original_filename: str
    authors: list[str]
    publication_year: int | None
    doi: str | None
    page_count: int | None


class ReportOut(BaseModel):
    id: str
    investigation_id: str
    title: str
    claim_text: str
    research_context: str | None
    verdict: Verdict
    explanation: str | None
    explanation_source: str | None
    reasons: list[str]
    evidence_summary: dict[str, Any]
    sources: list[ReportSource]
    supporting: list[EvidenceOut]
    contradicting: list[EvidenceOut]
    mixed: list[EvidenceOut]
    not_relevant: list[EvidenceOut]
    unassessed: list[EvidenceOut]
    methodology: list[str]
    limitations: list[str]
    model_identifier: str | None
    prompt_version: str | None
    methodology_version: str | None
    retrieval_configuration: dict[str, Any]
    assessed_at: datetime
    generated_at: datetime


class DashboardOut(BaseModel):
    documents_total: int
    documents_by_status: dict[str, int]
    investigations_total: int
    reports_total: int
    recent_investigations: list[InvestigationOut]
    recent_reports: list[ReportListItem]
    recent_documents: list[DocumentOut]
