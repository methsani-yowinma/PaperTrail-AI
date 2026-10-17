"""Deterministic verdict aggregation (no LLM involved).

Input: validated, citation-checked passage assessments. Output: one of SUPPORTED,
CONTRADICTED, MIXED_EVIDENCE, INCONCLUSIVE, plus the rule trace that produced it.

Rules (also in docs/AI_METHODOLOGY.md — keep both in sync and bump METHODOLOGY_VERSION):

R1  Only assessments whose citation validated are used. If more than half of the retrieved
    passages could not be assessed or validated, the verdict is INCONCLUSIVE.
R2  NOT_RELEVANT passages are ignored.
R3  A passage is *decisive* when it is DIRECT, its strength is STRONG or MODERATE, and its
    type is EXPERIMENTAL_RESULT, AUTHOR_CONCLUSION or OTHER. Cited prior work and background
    mentions are never decisive: they are not independent evidence.
R4  Passages are grouped into *sources*: documents sharing a DOI are one source, otherwise
    each document is one source. Several passages from one source count once.
R5  If decisive support and decisive contradiction both exist, or any decisive passage is
    MIXED, the verdict is MIXED_EVIDENCE.
R6  If only one side has decisive evidence but the other side has any DIRECT, non-background
    passage (even weak), the verdict is MIXED_EVIDENCE (conservative by design).
R7  Otherwise decisive support only → SUPPORTED; decisive contradiction only → CONTRADICTED.
R8  With no decisive evidence the verdict is INCONCLUSIVE.

Model-reported confidence is recorded but deliberately NOT used: it is not calibrated.
No numeric score is produced, so nothing here should be read as a probability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.records import Directness, EvidenceStrength, EvidenceType, PassageRelation, Verdict

DECISIVE_STRENGTHS = {EvidenceStrength.STRONG, EvidenceStrength.MODERATE}
DECISIVE_TYPES = {EvidenceType.EXPERIMENTAL_RESULT, EvidenceType.AUTHOR_CONCLUSION, EvidenceType.OTHER}
NON_INDEPENDENT_TYPES = {EvidenceType.CITED_PRIOR_WORK, EvidenceType.BACKGROUND_MENTION}


@dataclass(frozen=True)
class VerdictInput:
    """The subset of a passage assessment that aggregation is allowed to use."""

    passage_label: str
    document_id: str
    doi: str | None
    relation: PassageRelation
    directness: Directness
    evidence_strength: EvidenceStrength
    evidence_type: EvidenceType
    citation_valid: bool


@dataclass
class VerdictResult:
    verdict: Verdict
    reasons: list[str]
    limitations: list[str]
    summary: dict[str, Any] = field(default_factory=dict)


def _source_key(item: VerdictInput) -> str:
    return f"doi:{item.doi.strip().lower()}" if item.doi and item.doi.strip() else f"doc:{item.document_id}"


def _is_decisive(item: VerdictInput) -> bool:
    return (
        item.directness == Directness.DIRECT
        and item.evidence_strength in DECISIVE_STRENGTHS
        and item.evidence_type in DECISIVE_TYPES
    )


def aggregate_verdict(items: list[VerdictInput], *, retrieved_count: int) -> VerdictResult:
    reasons: list[str] = []
    limitations: list[str] = []

    if retrieved_count == 0:
        return VerdictResult(
            Verdict.INCONCLUSIVE,
            ["No sufficiently relevant passages were found in the selected documents."],
            ["The selected documents may not discuss this claim, or may use different terminology."],
            {"retrieved_passages": 0},
        )

    usable = [i for i in items if i.citation_valid]
    unusable = retrieved_count - len(usable)
    if unusable * 2 > retrieved_count:
        return VerdictResult(
            Verdict.INCONCLUSIVE,
            [f"{unusable} of {retrieved_count} retrieved passages could not be reliably assessed or validated (R1)."],
            ["The automated assessment output was incomplete, so no verdict was drawn."],
            {"retrieved_passages": retrieved_count, "usable_assessments": len(usable)},
        )
    if unusable:
        limitations.append(f"{unusable} retrieved passage(s) could not be assessed or validated and were excluded.")

    relevant = [i for i in usable if i.relation != PassageRelation.NOT_RELEVANT]
    decisive = [i for i in relevant if _is_decisive(i)]

    def sources(relation: PassageRelation, pool: list[VerdictInput]) -> set[str]:
        return {_source_key(i) for i in pool if i.relation == relation}

    support = sources(PassageRelation.SUPPORTS, decisive)
    contra = sources(PassageRelation.CONTRADICTS, decisive)
    mixed = sources(PassageRelation.MIXED, decisive)
    direct_non_background = [
        i for i in relevant if i.directness == Directness.DIRECT and i.evidence_type not in NON_INDEPENDENT_TYPES
    ]
    weak_direct_support = sources(PassageRelation.SUPPORTS, direct_non_background) - support
    weak_direct_contra = sources(PassageRelation.CONTRADICTS, direct_non_background) - contra

    summary: dict[str, Any] = {
        "retrieved_passages": retrieved_count,
        "usable_assessments": len(usable),
        "relevant_passages": len(relevant),
        "decisive_passages": len(decisive),
        "passages_by_relation": {
            r.value: sum(1 for i in usable if i.relation == r)
            for r in (PassageRelation.SUPPORTS, PassageRelation.CONTRADICTS, PassageRelation.MIXED, PassageRelation.NOT_RELEVANT)
        },
        "independent_sources": {
            "supporting": len(support),
            "contradicting": len(contra),
            "mixed": len(mixed),
            "all_relevant": len({_source_key(i) for i in relevant}),
        },
        "directness": {d.value: sum(1 for i in relevant if i.directness == d) for d in Directness},
        "strength": {s.value: sum(1 for i in relevant if i.evidence_strength == s) for s in EvidenceStrength},
    }

    non_decisive = len(relevant) - len(decisive)
    if non_decisive:
        limitations.append(
            f"{non_decisive} relevant passage(s) were indirect, weak, background mentions or citations of prior work; "
            "they were reported but did not determine the verdict."
        )
    if any(i.evidence_type == EvidenceType.CITED_PRIOR_WORK for i in relevant):
        limitations.append("Some passages cite earlier publications; these are not counted as independent confirmation.")

    if (support and contra) or mixed:
        if support and contra:
            reasons.append(
                f"Decisive evidence points both ways: {len(support)} source(s) support and {len(contra)} contradict the claim (R5)."
            )
        if mixed:
            reasons.append(f"{len(mixed)} source(s) report mixed or condition-dependent findings (R5).")
        return VerdictResult(Verdict.MIXED_EVIDENCE, reasons, limitations, summary)

    if support:
        if weak_direct_contra:
            reasons.append(
                f"{len(support)} source(s) provide decisive support, but {len(weak_direct_contra)} source(s) report direct, "
                "weaker contrary evidence (R6)."
            )
            return VerdictResult(Verdict.MIXED_EVIDENCE, reasons, limitations, summary)
        reasons.append(f"{len(support)} independent source(s) provide direct, decisive support; none contradicts it (R7).")
        if len(support) == 1:
            limitations.append("The verdict rests on a single source; independent replication was not found in the selection.")
        return VerdictResult(Verdict.SUPPORTED, reasons, limitations, summary)

    if contra:
        if weak_direct_support:
            reasons.append(
                f"{len(contra)} source(s) provide decisive contrary evidence, but {len(weak_direct_support)} source(s) report "
                "direct, weaker supporting evidence (R6)."
            )
            return VerdictResult(Verdict.MIXED_EVIDENCE, reasons, limitations, summary)
        reasons.append(f"{len(contra)} independent source(s) provide direct, decisive contrary evidence; none supports it (R7).")
        if len(contra) == 1:
            limitations.append("The verdict rests on a single source; independent replication was not found in the selection.")
        return VerdictResult(Verdict.CONTRADICTED, reasons, limitations, summary)

    if relevant:
        reasons.append("Relevant passages were found, but none provides direct, decisive evidence about the claim (R8).")
    else:
        reasons.append("All retrieved passages were assessed as not relevant to the claim (R8).")
    return VerdictResult(Verdict.INCONCLUSIVE, reasons, limitations, summary)


def template_explanation(verdict: Verdict, reasons: list[str]) -> str:
    """Deterministic fallback used when no model explanation is available."""
    lead = {
        Verdict.SUPPORTED: "Within the selected documents, the evidence supports the claim.",
        Verdict.CONTRADICTED: "Within the selected documents, the evidence contradicts the claim.",
        Verdict.MIXED_EVIDENCE: "Within the selected documents, the evidence is mixed.",
        Verdict.INCONCLUSIVE: "The selected documents do not provide enough direct evidence to reach a conclusion.",
    }[verdict]
    return " ".join([lead, *reasons])
