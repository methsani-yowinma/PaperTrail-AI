"""PaperTrail AI evaluation runner (independent of the UI).

Runs the real ingestion → retrieval → assessment → citation validation → verdict pipeline
on a hand-labelled SYNTHETIC dataset and reports retrieval, assessment, citation-integrity,
reliability and efficiency metrics.

Assessors:
  oracle  (default) a mock that returns the dataset's gold labels, optionally with seeded
          label noise. No network, no cost. It measures the deterministic parts of the
          system (retrieval, citation validation, aggregation) — NOT language-model quality.
  gemini  the real Gemini client configured in backend/.env (GOOGLE_API_KEY, GEMINI_MODEL).
          Makes paid API calls. Only this mode measures model assessment quality, and only
          on this small synthetic dataset.

Examples (run from the repository root):
  backend/.venv/Scripts/python evaluation/scripts/run_evaluation.py
  backend/.venv/Scripts/python evaluation/scripts/run_evaluation.py --noise 0.2 --seed 1
  backend/.venv/Scripts/python evaluation/scripts/run_evaluation.py --embedder sentence-transformers
  backend/.venv/Scripts/python evaluation/scripts/run_evaluation.py --assessor gemini \
      --input-price-per-1m 0.30 --output-price-per-1m 2.50
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import METHODOLOGY_VERSION, Settings  # noqa: E402
from app.core.container import build_container  # noqa: E402
from app.models.records import InvestigationStatus  # noqa: E402
from app.schemas.api import InvestigationCreate  # noqa: E402
from app.services.llm_client import LLMResponse  # noqa: E402
from app.services.prompts import PROMPT_VERSION  # noqa: E402
from tests.pdf_factory import make_pdf  # noqa: E402

OWNER = "00000000-0000-4000-8000-0000000000e1"
RELATIONS = ["SUPPORTS", "CONTRADICTS", "MIXED", "NOT_RELEVANT"]
VERDICTS = ["SUPPORTED", "CONTRADICTED", "MIXED_EVIDENCE", "INCONCLUSIVE"]


def key(text: str) -> str:
    return " ".join(text.split())[:80]


class OracleLLM:
    """Returns gold labels for each passage (optionally corrupted by seeded noise)."""

    model_identifier = "oracle-mock"

    def __init__(self, dataset: dict[str, Any], noise: float, seed: int):
        self.noise = noise
        self.rng = random.Random(seed)
        self.calls = 0
        self.passage_index = {
            key(text): (doc_key, page)
            for doc_key, doc in dataset["documents"].items()
            for page, text in enumerate(doc["pages"], start=1)
        }
        self.gold = {c["claim"]: {(g["doc"], g["page"]): g for g in c["gold"]} for c in dataset["claims"]}

    def generate_json(self, *, system_instruction: str, contents: str, response_model) -> LLMResponse:
        self.calls += 1
        if response_model.__name__ == "LLMExplanationResponse":
            return LLMResponse(json.dumps({"explanation": ""}))  # forces the deterministic template
        payload = json.loads(contents.split("\n\nYour previous answer")[0])
        gold = self.gold.get(payload["claim"], {})
        out = []
        for p in payload["passages"]:
            location = self.passage_index.get(key(p["text"]))
            g = gold.get(location) if location else None
            relation = g["relation"] if g else "NOT_RELEVANT"
            if self.noise and self.rng.random() < self.noise:
                relation = self.rng.choice([r for r in RELATIONS if r != relation])
            out.append({
                "passage_id": p["passage_id"], "relation": relation,
                "directness": g["directness"] if g else "INDIRECT",
                "evidence_strength": g["strength"] if g else "WEAK",
                "evidence_type": g["type"] if g else "BACKGROUND_MENTION",
                "rationale": "Oracle label from the evaluation dataset.",
                "quote": p["text"][:120] if relation != "NOT_RELEVANT" else "",
                "limitations": [], "confidence": None,
            })
        return LLMResponse(json.dumps({"assessments": out}))

    def check_model(self) -> dict[str, Any]:
        return {"model": self.model_identifier}


class MalformedLLM:
    model_identifier = "malformed-mock"

    def generate_json(self, **_: Any) -> LLMResponse:
        return LLMResponse('{"assessments": [{"passage_id": "P1", "relation": "TRUE!!"}')

    def check_model(self) -> dict[str, Any]:
        return {}


def prf(gold: list[str], pred: list[str], labels: list[str]) -> dict[str, Any]:
    per_class = {}
    for label in labels:
        tp = sum(1 for g, p in zip(gold, pred) if g == label and p == label)
        fp = sum(1 for g, p in zip(gold, pred) if g != label and p == label)
        fn = sum(1 for g, p in zip(gold, pred) if g == label and p != label)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        f1 = (2 * precision * recall / (precision + recall)) if precision and recall else (0.0 if (tp + fp + fn) else None)
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
    f1s = [v["f1"] for v in per_class.values() if v["f1"] is not None and v["support"] > 0]
    confusion = {g: {p: sum(1 for a, b in zip(gold, pred) if a == g and b == p) for p in labels} for g in labels}
    return {
        "n": len(gold),
        "accuracy": (sum(1 for g, p in zip(gold, pred) if g == p) / len(gold)) if gold else None,
        "macro_f1": statistics.fmean(f1s) if f1s else None,
        "per_class": per_class,
        "confusion_matrix": confusion,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="papertrail-eval-"))
    min_sim = args.min_similarity if args.min_similarity is not None else (0.35 if args.embedder == "hashing" else 0.60)
    settings = Settings(
        _env_file=None if args.assessor == "oracle" else str(ROOT / "backend" / ".env"),
        app_env="test", auth_mode="local", database_backend="sqlite", storage_backend="local",
        sqlite_path=tmp / "eval.db", local_storage_dir=tmp / "uploads", embedding_provider=args.embedder,
        retrieval_min_semantic_similarity=min_sim, retrieval_top_k=args.top_k,
        rate_limit_verify_per_minute=10_000, rate_limit_upload_per_minute=10_000,
    )
    if args.assessor == "gemini":
        if not settings.gemini_configured:
            raise SystemExit("GOOGLE_API_KEY and GEMINI_MODEL must be set in backend/.env for --assessor gemini.")
        llm = None
        container = build_container(settings, use_configured_llm=True)
    else:
        llm = OracleLLM(dataset, args.noise, args.seed)
        container = build_container(settings, llm=llm, use_configured_llm=False)
    container.repo.ensure_profile(OWNER, "evaluation")

    # ---- ingestion ---------------------------------------------------------------------
    doc_ids: dict[str, str] = {}
    processing_times: list[float] = []
    page_checks: list[bool] = []
    for doc_key, doc in dataset["documents"].items():
        pdf = make_pdf([[("p", text)] for text in doc["pages"]], title=doc["title"], author="; ".join(doc["authors"]),
                       subject=f"doi:{doc['doi']}" if doc["doi"] else None)
        record = container.documents.upload(OWNER, f"{doc_key}.pdf", "application/pdf", pdf)
        started = time.perf_counter()
        container.documents.process(OWNER, record.id)
        processing_times.append(time.perf_counter() - started)
        stored = container.documents.get(OWNER, record.id)
        doc_ids[doc_key] = record.id
        chunks = container.repo.list_chunks(OWNER, record.id)
        page_checks.append(stored.page_count == len(doc["pages"]))
        for chunk in chunks:
            page_checks.append(key(chunk.content) == key(doc["pages"][chunk.page_start - 1]))
    location_of = {doc_id: doc_key for doc_key, doc_id in doc_ids.items()}

    # ---- claims --------------------------------------------------------------------------
    per_claim = []
    rel_gold, rel_pred, verdict_gold, verdict_pred = [], [], [], []
    citations_total = citations_valid = quotes_total = quotes_verified = pages_valid = 0
    retrieval_rows = []
    for claim in dataset["claims"]:
        gold = {(g["doc"], g["page"]): g for g in claim["gold"]}
        relevant = {k for k, g in gold.items() if g["relation"] != "NOT_RELEVANT"}
        selected = [doc_ids[d] for d in claim["documents"]]

        retrieved = container.retrieval.retrieve(OWNER, claim["claim"], selected, args.top_k).passages
        ranked = [(location_of[p.document.id], p.chunk.page_start) for p in retrieved]
        hits = [loc in relevant for loc in ranked]
        first_hit = next((i for i, h in enumerate(hits, start=1) if h), None)
        retrieval_rows.append({
            "claim": claim["id"], "relevant": len(relevant), "retrieved": len(ranked),
            "recall_at_k": (sum(hits) / len(relevant)) if relevant else None,
            "precision_at_k": (sum(hits) / len(ranked)) if ranked and relevant else None,
            "reciprocal_rank": (1 / first_hit if first_hit else 0.0) if relevant else None,
            "empty_retrieval": not ranked,
        })

        inv = container.investigations.create(OWNER, InvestigationCreate(
            claim_text=claim["claim"], document_ids=selected, title=claim["id"], settings={"top_k": args.top_k}))
        started = time.perf_counter()
        _, assessment = container.investigations.verify(OWNER, inv.id)
        elapsed = time.perf_counter() - started
        evidence = container.investigations.evidence_views(OWNER, assessment)
        for e in evidence:
            loc = (location_of.get(e.citation.document_id or ""), e.citation.page_start)
            g = gold.get(loc)
            if e.relation.value != "UNASSESSED":
                rel_gold.append(g["relation"] if g else "NOT_RELEVANT")
                rel_pred.append(e.relation.value)
            citations_total += 1
            citations_valid += int(e.citation.valid)
            doc_pages = len(dataset["documents"][loc[0]]["pages"]) if loc[0] else 0
            pages_valid += int(bool(e.citation.page_start) and 1 <= e.citation.page_start <= doc_pages)
            if e.relation.value not in ("NOT_RELEVANT", "UNASSESSED"):
                quotes_total += 1
                quotes_verified += int(e.citation.excerpt_verified)
        predicted = assessment.verdict.value if assessment.verdict else "NONE"
        verdict_gold.append(claim["expected_verdict"])
        verdict_pred.append(predicted)
        summary = assessment.assessment_metadata.get("evidence_summary", {})
        per_claim.append({
            "id": claim["id"], "expected": claim["expected_verdict"], "predicted": predicted,
            "correct": predicted == claim["expected_verdict"],
            "llm_calls": assessment.assessment_metadata.get("llm_calls", 0),
            "seconds": round(elapsed, 3),
            "independent_supporting_sources": summary.get("independent_sources", {}).get("supporting"),
            "expected_supporting_sources": claim.get("expected_supporting_sources"),
            "expected_empty_retrieval": claim.get("expect_empty_retrieval", False),
            "status": assessment.status.value,
        })

    # ---- reliability checks --------------------------------------------------------------
    reliability: dict[str, Any] = {}
    c1 = next(c for c in dataset["claims"] if c["id"] == "C1")
    runs = []
    for _ in range(2):
        inv = container.investigations.create(OWNER, InvestigationCreate(
            claim_text=c1["claim"], document_ids=[doc_ids[d] for d in c1["documents"]], settings={"top_k": args.top_k}))
        _, a = container.investigations.verify(OWNER, inv.id)
        runs.append((a.verdict, [e.chunk_id for e in container.repo.list_evidence(OWNER, a.id)]))
    reliability["deterministic_repeat"] = runs[0] == runs[1] if args.assessor == "oracle" and not args.noise else "n/a (non-deterministic assessor)"

    malformed_container = build_container(settings, repo=container.repo, storage=container.storage,
                                          embedder=container.embedder, llm=MalformedLLM(), use_configured_llm=False)
    c2 = next(c for c in dataset["claims"] if c["id"] == "C2")
    inv = malformed_container.investigations.create(OWNER, InvestigationCreate(
        claim_text=c2["claim"], document_ids=[doc_ids[d] for d in c2["documents"]]))
    try:
        updated, a = malformed_container.investigations.verify(OWNER, inv.id)
        reliability["malformed_output"] = {
            "crashed": False, "verdict": a.verdict.value if a.verdict else None,
            "investigation_status": updated.status.value,
            "llm_calls": a.assessment_metadata.get("llm_calls"),
            "handled_safely": (a.verdict is None or a.verdict.value == "INCONCLUSIVE") and updated.status == InvestigationStatus.COMPLETED,
        }
    except Exception as exc:  # pragma: no cover - reported, not raised
        reliability["malformed_output"] = {"crashed": True, "error": type(exc).__name__, "handled_safely": False}

    empties = [c for c in per_claim if c["expected_empty_retrieval"]]
    reliability["empty_retrieval"] = [
        {"claim": c["id"], "verdict": c["predicted"], "llm_calls": c["llm_calls"],
         "handled_safely": c["predicted"] == "INCONCLUSIVE" and c["llm_calls"] == 0} for c in empties
    ]
    not_supported = [c for c in per_claim if c["expected"] != "SUPPORTED"]
    reliability["unsupported_claim_rate"] = (
        sum(1 for c in not_supported if c["predicted"] == "SUPPORTED") / len(not_supported) if not_supported else None
    )
    reliability["source_independence"] = [
        {"claim": c["id"], "expected": c["expected_supporting_sources"], "observed": c["independent_supporting_sources"]}
        for c in per_claim if c["expected_supporting_sources"] is not None
    ]

    # ---- efficiency ----------------------------------------------------------------------
    llm_calls = [c["llm_calls"] for c in per_claim]
    efficiency: dict[str, Any] = {
        "avg_document_processing_seconds": round(statistics.fmean(processing_times), 3),
        "avg_verification_seconds": round(statistics.fmean(c["seconds"] for c in per_claim), 3),
        "avg_llm_calls_per_investigation": round(statistics.fmean(llm_calls), 2),
        "estimated_cost_usd": None,
    }
    if args.assessor == "gemini" and args.input_price_per_1m is not None and args.output_price_per_1m is not None:
        usage = [u for row in container.repo.list_reports(OWNER, limit=1000)[0]
                 for u in row.assessment.assessment_metadata.get("llm_usage", [])]
        prompt = sum(u.get("prompt_tokens") or 0 for u in usage)
        output = sum((u.get("output_tokens") or 0) + (u.get("thinking_tokens") or 0) for u in usage)
        efficiency["estimated_cost_usd"] = round(prompt / 1e6 * args.input_price_per_1m + output / 1e6 * args.output_price_per_1m, 6)
        efficiency["tokens"] = {"prompt": prompt, "output_including_thinking": output, "note": "assessment calls only"}

    def mean(values):
        values = [v for v in values if v is not None]
        return round(statistics.fmean(values), 4) if values else None

    return {
        "label": "SYNTHETIC DATASET" + (" · ORACLE (MOCK) ASSESSOR" if args.assessor == "oracle" else " · GEMINI ASSESSOR"),
        "caveat": (
            "Synthetic, hand-written passages. With the oracle assessor, assessment metrics reflect injected noise only and "
            "do NOT measure language-model quality. None of these numbers describe real-world accuracy."
        ),
        "run": {
            "timestamp": datetime.now(timezone.utc).isoformat(), "dataset": dataset["name"], "assessor": args.assessor,
            "model": container.assessor.model_identifier, "noise": args.noise, "seed": args.seed,
            "embedder": container.embedder.model_id, "top_k": args.top_k, "min_semantic_similarity": min_sim,
            "methodology_version": METHODOLOGY_VERSION, "prompt_version": PROMPT_VERSION,
        },
        "retrieval": {
            "mean_recall_at_k": mean(r["recall_at_k"] for r in retrieval_rows),
            "mean_precision_at_k": mean(r["precision_at_k"] for r in retrieval_rows),
            "mrr": mean(r["reciprocal_rank"] for r in retrieval_rows),
            "per_claim": retrieval_rows,
        },
        "passage_assessment": prf(rel_gold, rel_pred, RELATIONS),
        "verdicts": prf(verdict_gold, verdict_pred, VERDICTS),
        "citation_integrity": {
            "citations": citations_total,
            "resolving_to_valid_passages": round(citations_valid / citations_total, 4) if citations_total else None,
            "quotations_matching_stored_text": round(quotes_verified / quotes_total, 4) if quotes_total else None,
            "valid_page_references": round(pages_valid / citations_total, 4) if citations_total else None,
            "ingestion_page_mapping_correct": round(sum(page_checks) / len(page_checks), 4),
        },
        "reliability": reliability,
        "efficiency": efficiency,
        "per_claim": per_claim,
    }


def fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def to_markdown(r: dict[str, Any]) -> str:
    lines = [f"# Evaluation run: {r['label']}", "", f"> {r['caveat']}", "", "## Run", ""]
    lines += [f"- **{k}**: {fmt(v)}" for k, v in r["run"].items()]
    rt = r["retrieval"]
    lines += ["", "## Retrieval", "", f"- Mean Recall@k: {fmt(rt['mean_recall_at_k'])}",
              f"- Mean Precision@k: {fmt(rt['mean_precision_at_k'])}", f"- MRR: {fmt(rt['mrr'])}", "",
              "| Claim | Relevant | Retrieved | Recall@k | Precision@k | RR |", "|---|---|---|---|---|---|"]
    lines += [f"| {x['claim']} | {x['relevant']} | {x['retrieved']} | {fmt(x['recall_at_k'])} | {fmt(x['precision_at_k'])} | {fmt(x['reciprocal_rank'])} |"
              for x in rt["per_claim"]]
    for title, block, labels in (("Passage assessment", r["passage_assessment"], RELATIONS), ("Verdicts", r["verdicts"], VERDICTS)):
        lines += ["", f"## {title}", "", f"- n = {block['n']}, accuracy = {fmt(block['accuracy'])}, macro-F1 = {fmt(block['macro_f1'])}", "",
                  "| Class | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
        lines += [f"| {c} | {fmt(m['precision'])} | {fmt(m['recall'])} | {fmt(m['f1'])} | {m['support']} |" for c, m in block["per_class"].items()]
        lines += ["", "Confusion matrix (rows = gold, columns = predicted):", "", "| gold \\ pred | " + " | ".join(labels) + " |",
                  "|---|" + "---|" * len(labels)]
        lines += [f"| {g} | " + " | ".join(str(block["confusion_matrix"][g][p]) for p in labels) + " |" for g in labels]
    lines += ["", "## Citation integrity", ""] + [f"- {k}: {fmt(v)}" for k, v in r["citation_integrity"].items()]
    lines += ["", "## Reliability", "", "```json", json.dumps(r["reliability"], indent=2), "```"]
    lines += ["", "## Efficiency", ""] + [f"- {k}: {fmt(v)}" for k, v in r["efficiency"].items() if k != "tokens"]
    lines += ["", "## Per claim", "", "| Claim | Expected | Predicted | Correct | LLM calls | Seconds |", "|---|---|---|---|---|---|"]
    lines += [f"| {c['id']} | {c['expected']} | {c['predicted']} | {'yes' if c['correct'] else 'no'} | {c['llm_calls']} | {c['seconds']} |"
              for c in r["per_claim"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default=str(ROOT / "evaluation" / "datasets" / "synthetic_v1.json"))
    parser.add_argument("--assessor", choices=["oracle", "gemini"], default="oracle")
    parser.add_argument("--embedder", choices=["hashing", "sentence-transformers"], default="hashing")
    parser.add_argument("--noise", type=float, default=0.0, help="oracle only: probability of corrupting each label")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--min-similarity", type=float, default=None)
    parser.add_argument("--input-price-per-1m", type=float, default=None, help="USD per 1M input tokens (for cost estimates)")
    parser.add_argument("--output-price-per-1m", type=float, default=None, help="USD per 1M output tokens")
    parser.add_argument("--out", default=str(ROOT / "evaluation" / "reports"))
    args = parser.parse_args()

    result = run(args)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{args.assessor}-{args.embedder}" + (f"-noise{args.noise}" if args.noise else "")
    (out / f"{stem}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out / f"{stem}.md").write_text(to_markdown(result), encoding="utf-8")
    print(to_markdown(result))
    print(f"Saved: {out / stem}.json and .md")


if __name__ == "__main__":
    main()
