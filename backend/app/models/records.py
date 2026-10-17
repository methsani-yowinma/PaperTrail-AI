"""Persistence-level records shared by every repository implementation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_OCR = "needs_ocr"


class InvestigationStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Verdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    MIXED_EVIDENCE = "MIXED_EVIDENCE"
    INCONCLUSIVE = "INCONCLUSIVE"


class PassageRelation(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    MIXED = "MIXED"
    NOT_RELEVANT = "NOT_RELEVANT"
    # Retrieved but never assessed (assessment unavailable, or the model's output for this
    # passage was rejected by validation).
    UNASSESSED = "UNASSESSED"


class Directness(str, Enum):
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"


class EvidenceStrength(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"


class EvidenceType(str, Enum):
    EXPERIMENTAL_RESULT = "EXPERIMENTAL_RESULT"
    AUTHOR_CONCLUSION = "AUTHOR_CONCLUSION"
    CITED_PRIOR_WORK = "CITED_PRIOR_WORK"
    BACKGROUND_MENTION = "BACKGROUND_MENTION"
    OTHER = "OTHER"


class AssessmentStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentRecord(BaseModel):
    id: str
    owner_id: str
    original_filename: str
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    doi: str | None = None
    source_url: str | None = None
    storage_path: str
    file_hash: str
    file_size_bytes: int
    page_count: int | None = None
    page_labels: list[str] | None = None
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    processing_error: str | None = None
    extraction_warnings: list[str] = Field(default_factory=list)
    metadata_sources: dict[str, str] = Field(default_factory=dict)
    embedding_model: str | None = None
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChunkRecord(BaseModel):
    id: str
    document_id: str
    owner_id: str
    chunk_index: int
    page_start: int
    page_end: int
    section_title: str | None = None
    content: str
    content_hash: str
    token_count: int
    embedding_model: str
    created_at: datetime


class NewChunk(BaseModel):
    """A chunk produced by ingestion, before persistence."""

    chunk_index: int
    page_start: int
    page_end: int
    section_title: str | None
    content: str
    content_hash: str
    token_count: int
    embedding: list[float]


class InvestigationRecord(BaseModel):
    id: str
    owner_id: str
    title: str
    claim_text: str
    research_context: str | None = None
    status: InvestigationStatus = InvestigationStatus.DRAFT
    overall_verdict: Verdict | None = None
    methodology_version: str
    settings: dict[str, Any] = Field(default_factory=dict)
    document_ids: list[str] = Field(default_factory=list)
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class AssessmentRecord(BaseModel):
    id: str
    investigation_id: str
    owner_id: str
    status: AssessmentStatus
    verdict: Verdict | None = None
    explanation: str | None = None
    limitations: list[str] = Field(default_factory=list)
    model_identifier: str | None = None
    prompt_version: str | None = None
    retrieval_configuration: dict[str, Any] = Field(default_factory=dict)
    assessment_metadata: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime


class EvidenceItemRecord(BaseModel):
    id: str
    assessment_id: str
    investigation_id: str
    owner_id: str
    # Nullable: the source document may be deleted after the assessment was made.
    document_id: str | None
    chunk_id: str | None
    retrieval_method: str
    retrieval_rank: int
    keyword_rank: int | None = None
    semantic_rank: int | None = None
    relevance_score: float
    semantic_similarity: float | None = None
    passage_relation: PassageRelation
    directness: Directness | None = None
    evidence_strength: EvidenceStrength | None = None
    evidence_type: EvidenceType | None = None
    model_confidence: float | None = None
    rationale: str | None = None
    limitations: list[str] = Field(default_factory=list)
    excerpt_start: int | None = None
    excerpt_end: int | None = None
    excerpt_verified: bool = False
    citation_valid: bool = False
    citation_issues: list[str] = Field(default_factory=list)
    created_at: datetime
