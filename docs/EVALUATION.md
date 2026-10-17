# Evaluation

The evaluation framework is independent of the UI. It runs the real backend pipeline
(ingestion, retrieval, assessment, citation validation, verdict aggregation) against a
labelled dataset and writes JSON and Markdown results to `evaluation/reports/`. That folder
is git-ignored except for its README.

```
evaluation/
  datasets/synthetic_v1.json     6 synthetic documents (12 one-passage pages) · 12 labelled claims
  scripts/run_evaluation.py      the runner
  reports/                       generated results (not committed)
```

## Important: what these numbers mean

- **All bundled data is synthetic.** The passages were written for this dataset and are not
  real research findings. The dataset is small (12 claims) and was labelled by the
  developer. Nothing measured here describes real-world accuracy.
- With the default **oracle assessor**, the "model" returns the gold labels (optionally
  corrupted with seeded noise). This tests the deterministic parts of the system: retrieval,
  citation validation, aggregation rules, reliability handling. It says **nothing about
  Gemini's quality**.
- Only `--assessor gemini` measures language-model assessment, and only on this tiny
  synthetic set. That mode makes paid API calls and has **not** been run during development
  (no API key was available).

## Dataset

Each page holds one passage, so gold labels are `(document, page)` pairs. The 12 claims
cover all four verdicts and these situations:

| Situation | Claims |
|---|---|
| Direct support | C2, C4, C8, C10, C11 |
| Direct contradiction (plus a cited-prior-work passage that must not count) | C3 |
| Conflicting sources | C1 |
| Condition-dependent finding (`MIXED`) | C5 |
| Only indirect/speculative evidence → INCONCLUSIVE | C7 |
| Wrong documents selected → empty retrieval, no model call | C6 |
| Related passages, none relevant → INCONCLUSIVE | C12 |
| Two uploads sharing one DOI → one independent source | C9 |

## Metrics

| Group | Metric | Definition |
|---|---|---|
| Retrieval | Recall@k, Precision@k, MRR | Against gold relevant passages (relation ≠ NOT_RELEVANT); claims without relevant passages are excluded from the means |
| Passage assessment | accuracy, macro-F1, per-class precision/recall, confusion matrix | Predicted vs gold relation for every assessed passage (unlisted passages are gold NOT_RELEVANT) |
| Verdicts | accuracy, macro-F1, per-class P/R, confusion matrix | Predicted vs expected verdict |
| Citation integrity | % citations resolving to valid passages; % quotations matching stored text; % valid page references; ingestion page-mapping correctness | Computed from stored evidence, not model output |
| Reliability | unsupported-claim rate; empty-retrieval handling; malformed-output handling; deterministic repeat | Unsupported-claim rate = share of claims whose expected verdict is not SUPPORTED but were predicted SUPPORTED |
| Efficiency | avg processing time per document; avg verification time; LLM calls per investigation; estimated cost | Cost is computed only for `--assessor gemini` when you pass `--input-price-per-1m` and `--output-price-per-1m` (prices change; none are hardcoded) |

## Running

```bash
# from the repository root
backend/.venv/Scripts/python evaluation/scripts/run_evaluation.py                       # oracle, hashing embedder
backend/.venv/Scripts/python evaluation/scripts/run_evaluation.py --noise 0.2 --seed 1  # corrupted labels
backend/.venv/Scripts/python evaluation/scripts/run_evaluation.py --embedder sentence-transformers
backend/.venv/Scripts/python evaluation/scripts/run_evaluation.py --assessor gemini \
    --embedder sentence-transformers --input-price-per-1m <USD> --output-price-per-1m <USD>
```

(macOS/Linux: `backend/.venv/bin/python`.)

## Results recorded during development (synthetic data)

These are the actual outputs of the commands above, run on 2026-10-18. They are recorded
to show the framework works and responds to errors. **They are not accuracy claims.**

| Run | Recall@k | Precision@k | MRR | Passage acc. | Verdict acc. | Citations valid | Quotes verified |
|---|---|---|---|---|---|---|---|
| Oracle, hashing embedder (test-only) | 0.950 | 1.000 | 1.000 | 1.000 (n=14) | 1.000 (n=12) | 1.000 | 1.000 |
| Oracle + 20 % label noise, hashing | 0.950 | 1.000 | 1.000 | 0.857 (n=14) | 0.917 (n=12) | 1.000 | 1.000 |
| Oracle, `bge-small-en-v1.5` | 1.000 | 0.725 | 1.000 | 1.000 (n=25) | 1.000 (n=12) | 1.000 | 1.000 |

Observations:

- The hashing embedder (lexical only) missed one indirect passage for C7. The real model
  recalled every relevant passage, but passed more marginal passages through the gate
  (lower precision); the assessor then marked them not relevant.
- With a perfect oracle, verdict accuracy is 1.0 by construction. This confirms that the
  aggregation rules match the hand-labelled expectations, not that any model is accurate.
- Reliability checks passed in all runs: the empty-retrieval claim gave INCONCLUSIVE with 0
  model calls; malformed model output gave INCONCLUSIVE without crashing (after one repair
  attempt); repeated runs were identical; the shared-DOI claim counted 1 supporting source;
  the unsupported-claim rate was 0.0.
- Efficiency with the oracle (Windows laptop, CPU): about 0.04 s per document with the
  hashing embedder and about 2.1 s with `bge-small` (including model warm-up); 1.67–1.75
  model calls per investigation.

## Extending the dataset

Add documents (one passage per page keeps labelling unambiguous) and claims with a `gold`
list of `{doc, page, relation, directness, strength, type}` and an `expected_verdict`. Keep
synthetic and real data in separate files. Do not commit private papers or labels derived
from them.
