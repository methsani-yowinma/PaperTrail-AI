"""Investigations and the verification pipeline.

verify():  retrieve ─► assess (LLM) ─► validate citations (DB) ─► aggregate verdict (rules)
           ─► explain (LLM, optional, falls back to template) ─► persist snapshot

Each run stores an immutable assessment snapshot (the basis of a report) with the retrieval
configuration, model identifier, prompt version and methodology version used.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from app.core.config import METHODOLOGY_VERSION, Settings
from app.core.errors import ConflictError, NotFoundError, ValidationFailed
from app.models.records import (
    AssessmentRecord,
    AssessmentStatus,
    ChunkRecord,
    DocumentRecord,
    EvidenceItemRecord,
    InvestigationRecord,
    InvestigationStatus,
    PassageRelation,
    ProcessingStatus,
    Verdict,
)
from app.repositories.base import Repository, utcnow
from app.schemas.api import (
    AssessmentOut,
    AssessmentSummary,
    CitationOut,
    DocumentRef,
    EvidenceOut,
    InvestigationCreate,
    InvestigationOut,
    RetrievalInfo,
)
from app.services.citation_validation_service import validate_citation
from app.services.claim_assessment_service import ClaimAssessmentService
from app.services.llm_client import LLMError
from app.services.retrieval_service import RetrievalService
from app.services.verdict_service import VerdictInput, aggregate_verdict, template_explanation

logger = logging.getLogger("papertrail.investigations")


def page_label(document: DocumentRecord | None, page: int | None) -> str | None:
    if document is None or page is None:
        return None
    labels = document.page_labels
    if labels and 1 <= page <= len(labels) and labels[page - 1]:
        return labels[page - 1]
    return str(page)


def format_reference(document: DocumentRecord, page_start: int, page_end: int) -> str:
    """Citation text built only from stored metadata."""
    authors = document.authors
    if not authors:
        who = None
    elif len(authors) == 1:
        who = authors[0]
    elif len(authors) == 2:
        who = f"{authors[0]} & {authors[1]}"
    else:
        who = f"{authors[0]} et al."
    year = f"({document.publication_year})" if document.publication_year else "(n.d.)"
    title = document.title or document.original_filename
    first, last = page_label(document, page_start), page_label(document, page_end)
    pages = f"p. {first}" if page_start == page_end else f"pp. {first}–{last}"
    parts = [f"{who} {year}." if who else f"{year}.", f"{title}.", f"{pages}."]
    if document.doi:
        parts.append(f"https://doi.org/{document.doi}")
    return " ".join(parts)


class InvestigationService:
    def __init__(
        self, settings: Settings, repo: Repository, retrieval: RetrievalService, assessor: ClaimAssessmentService
    ):
        self._settings = settings
        self._repo = repo
        self._retrieval = retrieval
        self._assessor = assessor

    # ---- CRUD ----------------------------------------------------------------------------
    def create(self, owner_id: str, body: InvestigationCreate) -> InvestigationRecord:
        documents = self._repo.get_documents(owner_id, body.document_ids)
        if len(documents) != len(body.document_ids):
            # Do not reveal whether the unknown IDs exist for another user.
            raise ValidationFailed("One or more selected documents were not found in your library.", code="unknown_documents")
        now = utcnow()
        title = (body.title or "").strip() or (body.claim_text[:97] + "…" if len(body.claim_text) > 100 else body.claim_text)
        record = InvestigationRecord(
            id=str(uuid.uuid4()),
            owner_id=owner_id,
            title=title,
            claim_text=body.claim_text,
            research_context=(body.research_context or "").strip() or None,
            status=InvestigationStatus.DRAFT,
            methodology_version=METHODOLOGY_VERSION,
            settings=body.settings.model_dump(),
            document_ids=body.document_ids,
            created_at=now,
            updated_at=now,
        )
        return self._repo.create_investigation(record)

    def get(self, owner_id: str, investigation_id: str) -> InvestigationRecord:
        inv = self._repo.get_investigation(owner_id, investigation_id)
        if inv is None:
            raise NotFoundError("Investigation not found.")
        return inv

    def delete(self, owner_id: str, investigation_id: str) -> None:
        inv = self.get(owner_id, investigation_id)
        if inv.status == InvestigationStatus.RUNNING:
            raise ConflictError("This investigation is running. Wait for it to finish before deleting it.")
        self._repo.delete_investigation(owner_id, investigation_id)

    def to_out(self, inv: InvestigationRecord, documents: dict[str, DocumentRecord] | None = None) -> InvestigationOut:
        if documents is None:
            documents = {d.id: d for d in self._repo.get_documents(inv.owner_id, inv.document_ids)}
        refs = [
            DocumentRef(
                id=d.id, title=d.title, original_filename=d.original_filename, authors=d.authors,
                publication_year=d.publication_year, processing_status=d.processing_status,
            )
            for doc_id in inv.document_ids
            if (d := documents.get(doc_id)) is not None
        ]
        latest = self._repo.get_latest_assessment(inv.owner_id, inv.id)
        return InvestigationOut(
            id=inv.id, title=inv.title, claim_text=inv.claim_text, research_context=inv.research_context,
            status=inv.status, overall_verdict=inv.overall_verdict, methodology_version=inv.methodology_version,
            settings=inv.settings, last_error=inv.last_error, documents=refs,
            missing_document_count=len(inv.document_ids) - len(refs),
            latest_assessment=AssessmentSummary(
                id=latest.id, status=latest.status, verdict=latest.verdict, created_at=latest.created_at,
                error_message=latest.error_message,
            ) if latest else None,
            created_at=inv.created_at, updated_at=inv.updated_at,
        )

    # ---- verification ---------------------------------------------------------------------
    def verify(self, owner_id: str, investigation_id: str) -> tuple[InvestigationRecord, AssessmentRecord]:
        inv = self.get(owner_id, investigation_id)
        documents = {d.id: d for d in self._repo.get_documents(owner_id, inv.document_ids)}
        searchable = [d for d in documents.values() if d.processing_status == ProcessingStatus.COMPLETED]
        if not searchable:
            raise ValidationFailed(
                "None of the selected documents has finished processing, so there is nothing to search.",
                code="no_searchable_documents",
            )
        if not self._repo.try_start_investigation(owner_id, investigation_id):
            raise ConflictError("This investigation is already being verified.", code="already_running")

        started = time.perf_counter()
        try:
            assessment = self._run_pipeline(owner_id, inv, documents)
        except Exception:
            logger.exception("Verification failed for investigation %s", investigation_id)
            self._repo.finish_investigation(
                owner_id, investigation_id, InvestigationStatus.FAILED, None,
                "Verification failed because of an internal error. Please try again.",
            )
            raise
        logger.info("Verification of %s finished in %.2fs", investigation_id, time.perf_counter() - started)
        return self.get(owner_id, investigation_id), assessment

    def _run_pipeline(self, owner_id: str, inv: InvestigationRecord, documents: dict[str, DocumentRecord]) -> AssessmentRecord:
        started = time.perf_counter()
        top_k = int(inv.settings.get("top_k") or self._settings.retrieval_top_k)
        retrieval = self._retrieval.retrieve(owner_id, inv.claim_text, inv.document_ids, top_k)
        retrieval_seconds = round(time.perf_counter() - started, 3)
        passages = retrieval.passages
        assessment_id = str(uuid.uuid4())
        now = utcnow()

        limitations: list[str] = []
        skipped = [d for d in documents.values() if d.processing_status != ProcessingStatus.COMPLETED]
        if skipped:
            limitations.append(
                f"{len(skipped)} selected document(s) were not searchable (not processed, failed, or needing OCR) and were not used."
            )
        if len(documents) < len(inv.document_ids):
            limitations.append("Some documents selected for this investigation have since been deleted.")

        metadata: dict[str, Any] = {
            "methodology_version": METHODOLOGY_VERSION,
            "retrieval_diagnostics": retrieval.diagnostics,
            "timings_seconds": {"retrieval": retrieval_seconds},
            "llm_calls": 0,
            "searched_document_ids": sorted(d.id for d in documents.values() if d.processing_status == ProcessingStatus.COMPLETED),
        }

        def evidence_row(p, rank: int, **fields: Any) -> EvidenceItemRecord:
            return EvidenceItemRecord(
                id=str(uuid.uuid4()), assessment_id=assessment_id, investigation_id=inv.id, owner_id=owner_id,
                document_id=p.document.id, chunk_id=p.chunk.id, retrieval_method=p.method, retrieval_rank=rank,
                keyword_rank=p.keyword_rank, semantic_rank=p.semantic_rank, relevance_score=p.fused_score,
                semantic_similarity=p.semantic_similarity, created_at=now, **fields,
            )

        # --- no relevant passages: INCONCLUSIVE without calling the model ---------------------
        if not passages:
            result = aggregate_verdict([], retrieved_count=0)
            assessment = AssessmentRecord(
                id=assessment_id, investigation_id=inv.id, owner_id=owner_id, status=AssessmentStatus.COMPLETED,
                verdict=result.verdict, explanation=template_explanation(result.verdict, result.reasons),
                limitations=limitations + result.limitations, model_identifier=None, prompt_version=None,
                retrieval_configuration=retrieval.configuration,
                assessment_metadata={**metadata, "reasons": result.reasons, "evidence_summary": result.summary,
                                     "explanation_source": "template"},
                created_at=now,
            )
            self._repo.save_assessment(assessment, [])
            self._repo.finish_investigation(owner_id, inv.id, InvestigationStatus.COMPLETED, result.verdict, None)
            return assessment

        # Citations are validated against the database independently of the model, on
        # every path (including when assessment fails).
        stored_chunks = {c.id: c for c in self._repo.get_chunks(owner_id, [p.chunk.id for p in passages])}
        stored_docs = {d.id: d for d in self._repo.get_documents(owner_id, list({p.document.id for p in passages}))}
        selected = set(inv.document_ids)

        def check_citation(p, quote: str | None):
            return validate_citation(
                owner_id=owner_id, selected_document_ids=selected, chunk=stored_chunks.get(p.chunk.id),
                document=stored_docs.get(p.document.id), quote=quote,
            )

        # --- assessment ------------------------------------------------------------------------
        try:
            outcome = self._assessor.assess(inv.claim_text, inv.research_context, passages)
        except LLMError as exc:
            # Keep what was retrieved so the user can still inspect the passages, but never
            # produce a verdict without an assessment.
            rows = []
            for p in passages:
                check = check_citation(p, None)
                rows.append(evidence_row(
                    p, p.rank, passage_relation=PassageRelation.UNASSESSED, citation_valid=check.valid,
                    citation_issues=check.issues,
                ))
            assessment = AssessmentRecord(
                id=assessment_id, investigation_id=inv.id, owner_id=owner_id, status=AssessmentStatus.FAILED,
                verdict=None, explanation=None, limitations=limitations,
                model_identifier=self._assessor.model_identifier, prompt_version=self._assessor.prompt_version,
                retrieval_configuration=retrieval.configuration,
                assessment_metadata={**metadata, "error_code": exc.code},
                error_message=exc.message, created_at=now,
            )
            self._repo.save_assessment(assessment, rows)
            self._repo.finish_investigation(owner_id, inv.id, InvestigationStatus.FAILED, None, exc.message)
            return assessment

        # --- citation validation against the database (independent of the model) ------------
        rows: list[EvidenceItemRecord] = []
        verdict_inputs: list[VerdictInput] = []
        for p in passages:
            a = outcome.assessments.get(p.chunk.id)
            doc = stored_docs.get(p.document.id)
            check = check_citation(p, a.quote if a else None)
            if a is None:
                rows.append(evidence_row(
                    p, p.rank, passage_relation=PassageRelation.UNASSESSED, citation_valid=check.valid,
                    citation_issues=check.issues + ["The model did not return a valid assessment for this passage."],
                ))
                continue
            rows.append(evidence_row(
                p, p.rank, passage_relation=a.relation, directness=a.directness, evidence_strength=a.evidence_strength,
                evidence_type=a.evidence_type, model_confidence=a.confidence, rationale=a.rationale,
                limitations=a.limitations, excerpt_start=check.excerpt_start, excerpt_end=check.excerpt_end,
                excerpt_verified=check.excerpt_verified, citation_valid=check.valid, citation_issues=check.issues,
            ))
            verdict_inputs.append(VerdictInput(
                passage_label=a.label, document_id=p.document.id, doi=doc.doi if doc else None, relation=a.relation,
                directness=a.directness, evidence_strength=a.evidence_strength, evidence_type=a.evidence_type,
                citation_valid=check.valid,
            ))

        result = aggregate_verdict(verdict_inputs, retrieved_count=len(passages))
        assessed = [a for a in outcome.assessments.values()]
        # Only ask for a prose explanation when there is relevant, validated evidence to explain.
        explainable = any(a.relation != PassageRelation.NOT_RELEVANT for a in assessed) and bool(verdict_inputs)
        explanation = (
            self._assessor.explain(inv.claim_text, result.verdict.value, result.reasons, assessed) if explainable else None
        )
        llm_calls = outcome.llm_calls + (1 if explainable else 0)
        explanation_source = "model" if explanation else "template"
        if not explanation:
            explanation = template_explanation(result.verdict, result.reasons)
        injection_flags = sum(1 for a in assessed if any("embedded instructions" in lim.lower() for lim in a.limitations))
        if injection_flags:
            limitations.append(f"{injection_flags} passage(s) contained embedded instructions; they were treated only as data.")

        assessment = AssessmentRecord(
            id=assessment_id, investigation_id=inv.id, owner_id=owner_id, status=AssessmentStatus.COMPLETED,
            verdict=result.verdict, explanation=explanation, limitations=limitations + result.limitations,
            model_identifier=self._assessor.model_identifier, prompt_version=self._assessor.prompt_version,
            retrieval_configuration=retrieval.configuration,
            assessment_metadata={
                **metadata,
                "llm_calls": llm_calls,
                "llm_usage": outcome.usage,
                "rejected_model_items": outcome.rejected,
                "missing_labels": outcome.missing_labels,
                "label_map": outcome.labels,
                "reasons": result.reasons,
                "evidence_summary": result.summary,
                "explanation_source": explanation_source,
                "timings_seconds": {"retrieval": retrieval_seconds, "assessment": outcome.duration_seconds,
                                    "total": round(time.perf_counter() - started, 3)},
            },
            created_at=now,
        )
        self._repo.save_assessment(assessment, rows)
        self._repo.finish_investigation(owner_id, inv.id, InvestigationStatus.COMPLETED, result.verdict, None)
        return assessment

    # ---- read models -----------------------------------------------------------------------
    def latest_assessment(self, owner_id: str, investigation_id: str, *, completed_only: bool = False) -> AssessmentRecord:
        self.get(owner_id, investigation_id)
        assessment = self._repo.get_latest_assessment(owner_id, investigation_id, completed_only=completed_only)
        if assessment is None:
            raise NotFoundError("This investigation has not been verified yet." if not completed_only
                                else "No completed assessment exists for this investigation yet.")
        return assessment

    def evidence_views(self, owner_id: str, assessment: AssessmentRecord) -> list[EvidenceOut]:
        items = self._repo.list_evidence(owner_id, assessment.id)
        chunks: dict[str, ChunkRecord] = {
            c.id: c for c in self._repo.get_chunks(owner_id, [i.chunk_id for i in items if i.chunk_id])
        }
        docs: dict[str, DocumentRecord] = {
            d.id: d for d in self._repo.get_documents(owner_id, list({i.document_id for i in items if i.document_id}))
        }
        out = []
        for item in items:
            chunk = chunks.get(item.chunk_id or "")
            doc = docs.get(item.document_id or "")
            issues = list(item.citation_issues)
            valid = item.citation_valid
            if chunk is None or doc is None:
                # The source was deleted (or reprocessed into different passages) after the assessment.
                valid = False
                issues = ["The source passage is no longer available (the document was deleted or reprocessed)."]
            excerpt_text = None
            if chunk and item.excerpt_verified and item.excerpt_start is not None and item.excerpt_end is not None:
                if 0 <= item.excerpt_start < item.excerpt_end <= len(chunk.content):
                    excerpt_text = chunk.content[item.excerpt_start:item.excerpt_end]
            out.append(EvidenceOut(
                id=item.id,
                label=f"P{item.retrieval_rank}",
                relation=item.passage_relation,
                directness=item.directness,
                evidence_strength=item.evidence_strength,
                evidence_type=item.evidence_type,
                model_confidence=item.model_confidence,
                rationale=item.rationale,
                limitations=item.limitations,
                retrieval=RetrievalInfo(
                    method=item.retrieval_method, rank=item.retrieval_rank, keyword_rank=item.keyword_rank,
                    semantic_rank=item.semantic_rank, fused_score=item.relevance_score,
                    semantic_similarity=item.semantic_similarity,
                ),
                citation=CitationOut(
                    valid=valid,
                    issues=issues,
                    document_id=doc.id if doc else None,
                    chunk_id=chunk.id if chunk else None,
                    document_title=doc.title if doc else None,
                    original_filename=doc.original_filename if doc else None,
                    authors=doc.authors if doc else [],
                    publication_year=doc.publication_year if doc else None,
                    doi=doc.doi if doc else None,
                    page_start=chunk.page_start if chunk else None,
                    page_end=chunk.page_end if chunk else None,
                    page_label=page_label(doc, chunk.page_start) if chunk else None,
                    section_title=chunk.section_title if chunk else None,
                    passage_text=chunk.content if chunk and doc else None,
                    excerpt_start=item.excerpt_start if excerpt_text else None,
                    excerpt_end=item.excerpt_end if excerpt_text else None,
                    excerpt_verified=excerpt_text is not None,
                    excerpt_text=excerpt_text,
                    reference=format_reference(doc, chunk.page_start, chunk.page_end) if chunk and doc else None,
                ),
            ))
        return out

    def assessment_out(self, owner_id: str, assessment: AssessmentRecord) -> AssessmentOut:
        meta = assessment.assessment_metadata
        return AssessmentOut(
            id=assessment.id,
            investigation_id=assessment.investigation_id,
            status=assessment.status,
            verdict=assessment.verdict,
            explanation=assessment.explanation,
            explanation_source=meta.get("explanation_source"),
            limitations=assessment.limitations,
            reasons=meta.get("reasons", []),
            evidence_summary=meta.get("evidence_summary", {}),
            model_identifier=assessment.model_identifier,
            prompt_version=assessment.prompt_version,
            methodology_version=meta.get("methodology_version"),
            retrieval_configuration=assessment.retrieval_configuration,
            metadata={k: meta[k] for k in ("llm_calls", "timings_seconds", "retrieval_diagnostics", "rejected_model_items",
                                            "missing_labels", "error_code") if k in meta},
            error_message=assessment.error_message,
            created_at=assessment.created_at,
            evidence=self.evidence_views(owner_id, assessment),
        )
