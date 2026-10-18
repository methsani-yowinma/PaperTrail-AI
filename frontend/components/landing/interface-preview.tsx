import { VerdictBadge } from "@/components/common/status-badges";
import { EvidenceCard } from "@/components/evidence/evidence-card";
import type { Evidence } from "@/types/api";

/*
 * A preview of the results interface, rendered with the same components the app uses.
 * The document, passage and assessment below are invented examples, labelled as such in
 * the UI. chunk_id is null so the card shows no "View in document" link to a fake record.
 */
const PASSAGE =
  "In our experiments, applying dropout with rate 0.5 reduced overfitting on all five benchmarks: the gap between training and validation accuracy fell from 14.2 to 3.1 percentage points.";
const EXCERPT = "applying dropout with rate 0.5 reduced overfitting on all five benchmarks";
const EXCERPT_START = PASSAGE.indexOf(EXCERPT);

const EXAMPLE_EVIDENCE: Evidence = {
  id: "example-p1",
  label: "P1",
  relation: "SUPPORTS",
  directness: "DIRECT",
  evidence_strength: "STRONG",
  evidence_type: "EXPERIMENTAL_RESULT",
  model_confidence: 0.86,
  rationale: "Reports a measured reduction in the train–validation gap under the stated conditions.",
  limitations: [],
  retrieval: { method: "hybrid", rank: 1, keyword_rank: 1, semantic_rank: 1, fused_score: 0.0328, semantic_similarity: 0.82 },
  citation: {
    valid: true,
    issues: [],
    document_id: "example-document",
    chunk_id: null,
    document_title: "Example paper A",
    original_filename: "example-a.pdf",
    authors: [],
    publication_year: null,
    doi: null,
    page_start: 6,
    page_end: 6,
    page_label: "6",
    section_title: "4 Results",
    passage_text: PASSAGE,
    excerpt_start: EXCERPT_START,
    excerpt_end: EXCERPT_START + EXCERPT.length,
    excerpt_verified: true,
    excerpt_text: EXCERPT,
    reference: "(n.d.). Example paper A. p. 6.",
  },
};

export function InterfacePreview() {
  return (
    <figure aria-label="Preview of the results interface using example data, not a real verification result" className="min-w-0">
      <div className="overflow-hidden rounded-lg border border-border bg-card shadow-raised">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-4 py-2.5">
          <span className="eyebrow text-academic">Investigation · results</span>
          <span className="rounded-[4px] border border-inconclusive/30 bg-inconclusive-soft px-1.5 py-0.5 font-mono text-[10.5px] font-medium text-inconclusive">
            Example data
          </span>
        </div>
        <div className="space-y-3 bg-background p-3 sm:p-4">
          <div className="rounded-md border border-border border-l-[3px] border-l-academic bg-card px-3.5 py-2.5">
            <p className="eyebrow text-[10px]">Claim under examination</p>
            <p className="mt-0.5 text-[14.5px] leading-snug">Dropout regularization reduces overfitting in neural networks.</p>
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-md border border-border bg-card px-3.5 py-2.5">
            <span className="eyebrow text-[10px]">Finding</span>
            <VerdictBadge verdict="SUPPORTED" />
            <span className="font-mono text-[11px] text-muted-foreground">R7 · 1 source supports, none contradicts</span>
          </div>
          <EvidenceCard evidence={EXAMPLE_EVIDENCE} />
        </div>
      </div>
      <figcaption className="mt-3 text-center text-xs leading-relaxed text-muted-foreground">
        Rendered with the app&apos;s own components. The document, passage and assessment are examples, not a real result.
      </figcaption>
    </figure>
  );
}
