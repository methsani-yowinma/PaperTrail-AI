from app.models.records import Directness as D
from app.models.records import EvidenceStrength as S
from app.models.records import EvidenceType as T
from app.models.records import PassageRelation as R
from app.models.records import Verdict
from app.services.verdict_service import VerdictInput, aggregate_verdict, template_explanation


def item(relation, doc="d1", *, directness=D.DIRECT, strength=S.STRONG, etype=T.EXPERIMENTAL_RESULT, doi=None, valid=True, label="P1"):
    return VerdictInput(label, doc, doi, relation, directness, strength, etype, valid)


def test_only_supporting_evidence_is_supported():
    result = aggregate_verdict([item(R.SUPPORTS, "d1"), item(R.SUPPORTS, "d2")], retrieved_count=2)
    assert result.verdict == Verdict.SUPPORTED
    assert result.summary["independent_sources"]["supporting"] == 2
    assert not any("single source" in lim for lim in result.limitations)


def test_only_contradicting_evidence_is_contradicted():
    result = aggregate_verdict([item(R.CONTRADICTS, "d1"), item(R.NOT_RELEVANT, "d2")], retrieved_count=2)
    assert result.verdict == Verdict.CONTRADICTED
    assert any("single source" in lim for lim in result.limitations)


def test_strong_conflicting_evidence_is_mixed():
    result = aggregate_verdict([item(R.SUPPORTS, "d1"), item(R.CONTRADICTS, "d2")], retrieved_count=2)
    assert result.verdict == Verdict.MIXED_EVIDENCE
    assert "R5" in result.reasons[0]


def test_decisive_mixed_passage_is_mixed():
    assert aggregate_verdict([item(R.MIXED, "d1")], retrieved_count=1).verdict == Verdict.MIXED_EVIDENCE


def test_weak_direct_contradiction_makes_support_mixed():
    items = [item(R.SUPPORTS, "d1"), item(R.CONTRADICTS, "d2", strength=S.WEAK)]
    result = aggregate_verdict(items, retrieved_count=2)
    assert result.verdict == Verdict.MIXED_EVIDENCE
    assert "R6" in result.reasons[0]


def test_indirect_contradiction_does_not_override_direct_support():
    items = [item(R.SUPPORTS, "d1"), item(R.CONTRADICTS, "d2", directness=D.INDIRECT)]
    assert aggregate_verdict(items, retrieved_count=2).verdict == Verdict.SUPPORTED


def test_irrelevant_passages_are_inconclusive():
    result = aggregate_verdict([item(R.NOT_RELEVANT, "d1"), item(R.NOT_RELEVANT, "d2")], retrieved_count=2)
    assert result.verdict == Verdict.INCONCLUSIVE
    assert "not relevant" in result.reasons[0]


def test_no_passages_is_inconclusive():
    result = aggregate_verdict([], retrieved_count=0)
    assert result.verdict == Verdict.INCONCLUSIVE


def test_insufficient_weak_or_indirect_evidence_is_inconclusive():
    items = [
        item(R.SUPPORTS, "d1", strength=S.WEAK),
        item(R.SUPPORTS, "d2", directness=D.INDIRECT),
        item(R.SUPPORTS, "d3", etype=T.BACKGROUND_MENTION),
    ]
    result = aggregate_verdict(items, retrieved_count=3)
    assert result.verdict == Verdict.INCONCLUSIVE
    assert any("did not determine the verdict" in lim for lim in result.limitations)


def test_cited_prior_work_is_not_independent_evidence():
    items = [item(R.SUPPORTS, "d1", etype=T.CITED_PRIOR_WORK), item(R.SUPPORTS, "d2", etype=T.CITED_PRIOR_WORK)]
    result = aggregate_verdict(items, retrieved_count=2)
    assert result.verdict == Verdict.INCONCLUSIVE
    assert any("earlier publications" in lim for lim in result.limitations)


def test_duplicate_sources_count_once():
    # Two passages of one document, plus a second upload of the same paper (same DOI).
    items = [
        item(R.SUPPORTS, "d1", doi="10.1/abc"),
        item(R.SUPPORTS, "d1", doi="10.1/abc", label="P2"),
        item(R.SUPPORTS, "d2", doi="10.1/ABC", label="P3"),
    ]
    result = aggregate_verdict(items, retrieved_count=3)
    assert result.verdict == Verdict.SUPPORTED
    assert result.summary["independent_sources"]["supporting"] == 1
    assert any("single source" in lim for lim in result.limitations)


def test_malformed_or_invalid_assessments_make_result_inconclusive():
    # 3 retrieved passages but only one usable assessment (others missing/invalid citations).
    items = [item(R.SUPPORTS, "d1"), item(R.SUPPORTS, "d2", valid=False)]
    result = aggregate_verdict(items, retrieved_count=3)
    assert result.verdict == Verdict.INCONCLUSIVE
    assert "R1" in result.reasons[0]


def test_minor_invalid_assessments_are_reported_but_tolerated():
    items = [item(R.SUPPORTS, "d1"), item(R.SUPPORTS, "d2"), item(R.SUPPORTS, "d3", valid=False)]
    result = aggregate_verdict(items, retrieved_count=3)
    assert result.verdict == Verdict.SUPPORTED
    assert any("could not be assessed" in lim for lim in result.limitations)


def test_aggregation_is_deterministic_and_order_independent():
    items = [item(R.SUPPORTS, "d1"), item(R.CONTRADICTS, "d2", strength=S.WEAK), item(R.NOT_RELEVANT, "d3")]
    first = aggregate_verdict(items, retrieved_count=3)
    second = aggregate_verdict(list(reversed(items)), retrieved_count=3)
    assert first.verdict == second.verdict and first.summary == second.summary


def test_template_explanation_never_claims_truth():
    for verdict in Verdict:
        text = template_explanation(verdict, ["reason"])
        assert "true" not in text.lower()
