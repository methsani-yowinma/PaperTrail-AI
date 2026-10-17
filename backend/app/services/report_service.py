"""Evidence reports, assembled deterministically from a stored assessment snapshot.

No LLM call happens here: a report only re-presents what was stored when the assessment
ran (verdict, explanation, validated evidence and source metadata).
"""

from __future__ import annotations

from app.core.errors import NotFoundError
from app.models.records import AssessmentStatus, PassageRelation
from app.repositories.base import Repository, utcnow
from app.schemas.api import EvidenceOut, ReportListItem, ReportOut, ReportSource
from app.services.investigation_service import InvestigationService

VERDICT_LABELS = {
    "SUPPORTED": "Supported",
    "CONTRADICTED": "Contradicted",
    "MIXED_EVIDENCE": "Mixed evidence",
    "INCONCLUSIVE": "Inconclusive",
}


class ReportService:
    def __init__(self, repo: Repository, investigations: InvestigationService):
        self._repo = repo
        self._investigations = investigations

    def list(self, owner_id: str, limit: int, offset: int) -> tuple[list[ReportListItem], int]:
        rows, total = self._repo.list_reports(owner_id, limit=limit, offset=offset)
        return [
            ReportListItem(
                id=r.assessment.id, investigation_id=r.assessment.investigation_id, investigation_title=r.investigation_title,
                claim_text=r.claim_text, verdict=r.assessment.verdict, created_at=r.assessment.created_at,
            )
            for r in rows
        ], total

    def for_investigation(self, owner_id: str, investigation_id: str) -> ReportOut:
        assessment = self._investigations.latest_assessment(owner_id, investigation_id, completed_only=True)
        return self.build(owner_id, assessment.id)

    def build(self, owner_id: str, report_id: str) -> ReportOut:
        assessment = self._repo.get_assessment(owner_id, report_id)
        if assessment is None or assessment.status != AssessmentStatus.COMPLETED or assessment.verdict is None:
            raise NotFoundError("Report not found.")
        inv = self._investigations.get(owner_id, assessment.investigation_id)
        evidence = self._investigations.evidence_views(owner_id, assessment)
        meta = assessment.assessment_metadata
        searched = meta.get("searched_document_ids") or inv.document_ids
        documents = self._repo.get_documents(owner_id, searched)
        config = assessment.retrieval_configuration

        def by(relation: PassageRelation) -> list[EvidenceOut]:
            return [e for e in evidence if e.relation == relation]

        methodology = [
            f"Searched {len(documents)} selected document(s) with hybrid retrieval: full-text keyword search "
            f"({config.get('keyword_backend', 'n/a')}) and semantic search ({config.get('vector_backend', 'n/a')}, "
            f"embedding model {config.get('embedding_model', 'n/a')}), fused with reciprocal rank fusion "
            f"(k={config.get('rrf_k', 'n/a')}).",
            f"Kept up to {config.get('top_k', 'n/a')} passages (at most {config.get('max_passages_per_document', 'n/a')} "
            "per document) that passed a relevance gate; duplicates were removed.",
        ]
        if assessment.model_identifier:
            methodology.append(
                f"Each passage was assessed individually by {assessment.model_identifier} (prompt {assessment.prompt_version}) "
                "with structured output validated against a strict schema; passage text was treated as untrusted data."
            )
        else:
            methodology.append("No language model was called because no sufficiently relevant passages were found.")
        methodology += [
            "Every citation was checked against the database: the passage, its document, ownership, selection and page range.",
            "Quotations are shown only when they were found verbatim (after whitespace/punctuation normalisation) in the stored passage.",
            f"The overall verdict was computed by deterministic rules (methodology {meta.get('methodology_version', 'n/a')}); "
            "model-reported confidence was not used.",
        ]

        return ReportOut(
            id=assessment.id,
            investigation_id=inv.id,
            title=inv.title,
            claim_text=inv.claim_text,
            research_context=inv.research_context,
            verdict=assessment.verdict,
            explanation=assessment.explanation,
            explanation_source=meta.get("explanation_source"),
            reasons=meta.get("reasons", []),
            evidence_summary=meta.get("evidence_summary", {}),
            sources=[
                ReportSource(
                    document_id=d.id, title=d.title, original_filename=d.original_filename, authors=d.authors,
                    publication_year=d.publication_year, doi=d.doi, page_count=d.page_count,
                )
                for d in documents
            ],
            supporting=by(PassageRelation.SUPPORTS),
            contradicting=by(PassageRelation.CONTRADICTS),
            mixed=by(PassageRelation.MIXED),
            not_relevant=by(PassageRelation.NOT_RELEVANT),
            unassessed=by(PassageRelation.UNASSESSED),
            methodology=methodology,
            limitations=assessment.limitations
            + ["This report assesses only the selected documents. It does not establish scientific truth."],
            model_identifier=assessment.model_identifier,
            prompt_version=assessment.prompt_version,
            methodology_version=meta.get("methodology_version"),
            retrieval_configuration=config,
            assessed_at=assessment.created_at,
            generated_at=utcnow(),
        )


def _evidence_markdown(items: list[EvidenceOut]) -> list[str]:
    if not items:
        return ["_None._", ""]
    lines: list[str] = []
    for e in items:
        c = e.citation
        lines.append(f"**[{e.label}]** {c.reference or 'Source unavailable'}")
        if c.section_title:
            lines.append(f"- Section: {c.section_title}")
        if e.directness or e.evidence_strength or e.evidence_type:
            lines.append(
                f"- Assessment: {e.directness.value if e.directness else '—'} · "
                f"{e.evidence_strength.value if e.evidence_strength else '—'} · "
                f"{e.evidence_type.value.replace('_', ' ').lower() if e.evidence_type else '—'}"
            )
        if e.rationale:
            lines.append(f"- Rationale (model): {e.rationale}")
        if c.excerpt_text:
            lines.append(f"- Verified excerpt: “{c.excerpt_text}”")
        elif c.passage_text:
            snippet = c.passage_text[:400] + ("…" if len(c.passage_text) > 400 else "")
            lines.append(f"- Stored passage (no verified quotation): “{snippet}”")
        if not c.valid:
            lines.append(f"- Citation issue: {'; '.join(c.issues)}")
        lines.append("")
    return lines


def report_to_markdown(report: ReportOut) -> str:
    lines = [
        f"# Evidence report: {report.title}",
        "",
        f"- **Claim:** {report.claim_text}",
        f"- **Verdict:** {VERDICT_LABELS[report.verdict.value]} (`{report.verdict.value}`)",
        f"- **Assessed:** {report.assessed_at.isoformat()}",
        f"- **Model:** {report.model_identifier or 'none'} · prompt {report.prompt_version or 'n/a'} · "
        f"methodology {report.methodology_version or 'n/a'}",
        "",
    ]
    if report.research_context:
        lines += ["## Research context", "", report.research_context, ""]
    lines += ["## Explanation", "", report.explanation or "_No explanation stored._", ""]
    if report.reasons:
        lines += ["### Rules applied", ""] + [f"- {r}" for r in report.reasons] + [""]
    lines += ["## Sources", ""]
    for s in report.sources:
        authors = ", ".join(s.authors) if s.authors else "Unknown authors"
        year = s.publication_year or "n.d."
        doi = f" https://doi.org/{s.doi}" if s.doi else ""
        lines.append(f"- {authors} ({year}). {s.title or s.original_filename}. {s.page_count or '?'} pages.{doi}")
    lines.append("")
    lines += ["## Supporting evidence", ""] + _evidence_markdown(report.supporting)
    lines += ["## Contradicting evidence", ""] + _evidence_markdown(report.contradicting)
    lines += ["## Mixed findings", ""] + _evidence_markdown(report.mixed)
    if report.unassessed:
        lines += ["## Retrieved but not assessed", ""] + _evidence_markdown(report.unassessed)
    lines += ["## Methodology", ""] + [f"- {m}" for m in report.methodology] + [""]
    lines += ["## Limitations", ""] + [f"- {lim}" for lim in report.limitations] + [""]
    lines += [f"_Generated by PaperTrail AI on {report.generated_at.isoformat()} from stored assessment data._", ""]
    return "\n".join(lines)
