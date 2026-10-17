import type { Evidence } from "@/types/api";

export const PASSAGE = "In our experiments, applying dropout with rate 0.5 reduced overfitting across all benchmarks.";

export function makeEvidence(overrides: Partial<Evidence> = {}, citation: Partial<Evidence["citation"]> = {}): Evidence {
  const start = PASSAGE.indexOf("applying dropout");
  const end = start + "applying dropout with rate 0.5 reduced overfitting".length;
  return {
    id: "ev-1",
    label: "P1",
    relation: "SUPPORTS",
    directness: "DIRECT",
    evidence_strength: "STRONG",
    evidence_type: "EXPERIMENTAL_RESULT",
    model_confidence: 0.82,
    rationale: "Reports a measured reduction in the generalisation gap.",
    limitations: ["Image benchmarks only."],
    retrieval: { method: "hybrid", rank: 1, keyword_rank: 1, semantic_rank: 2, fused_score: 0.0325, semantic_similarity: 0.81 },
    citation: {
      valid: true,
      issues: [],
      document_id: "doc-1",
      chunk_id: "chunk-1",
      document_title: "Dropout in Practice",
      original_filename: "dropout.pdf",
      authors: ["Ada Lovelace", "Alan Turing"],
      publication_year: 2021,
      doi: null,
      page_start: 4,
      page_end: 4,
      page_label: "4",
      section_title: "4 Results",
      passage_text: PASSAGE,
      excerpt_start: start,
      excerpt_end: end,
      excerpt_verified: true,
      excerpt_text: PASSAGE.slice(start, end),
      reference: "Ada Lovelace & Alan Turing (2021). Dropout in Practice. p. 4.",
      ...citation,
    },
    ...overrides,
  };
}
