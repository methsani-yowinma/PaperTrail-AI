import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { RelationBadge, VerdictBadge } from "@/components/common/status-badges";
import { EvidenceCard, EvidenceGroup, sourceHref } from "@/components/evidence/evidence-card";
import { HighlightedPassage } from "@/components/evidence/highlighted-passage";
import { VerdictPanel } from "@/components/evidence/verdict-panel";
import type { Verdict } from "@/types/api";

import { makeEvidence, PASSAGE } from "./fixtures";

describe("VerdictBadge", () => {
  it.each<[Verdict, string]>([
    ["SUPPORTED", "Supported"],
    ["CONTRADICTED", "Contradicted"],
    ["MIXED_EVIDENCE", "Mixed evidence"],
    ["INCONCLUSIVE", "Inconclusive"],
  ])("renders a text label and an icon for %s (never colour alone)", (verdict, label) => {
    const { container } = render(<VerdictBadge verdict={verdict} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("labels unassessed passages explicitly", () => {
    render(<RelationBadge relation="UNASSESSED" />);
    expect(screen.getByText("Not assessed")).toBeInTheDocument();
  });
});

describe("HighlightedPassage", () => {
  it("highlights exactly the verified offsets", () => {
    const { container } = render(<HighlightedPassage text={PASSAGE} start={20} end={36} />);
    expect(container.querySelector("mark")?.textContent).toBe(PASSAGE.slice(20, 36));
    expect(container.textContent).toBe(PASSAGE);
  });

  it.each([
    [null, null],
    [10, 5],
    [-1, 4],
    [0, PASSAGE.length + 10],
  ])("does not highlight invalid offsets (%s, %s)", (start, end) => {
    const { container } = render(<HighlightedPassage text={PASSAGE} start={start} end={end} />);
    expect(container.querySelector("mark")).toBeNull();
    expect(container.textContent).toBe(PASSAGE);
  });
});

describe("EvidenceCard", () => {
  it("shows the verified excerpt, source metadata, page and a link to the cited passage", () => {
    render(<EvidenceCard evidence={makeEvidence()} />);
    const card = screen.getByRole("article", { name: "Evidence P1" });
    expect(within(card).getByText("Dropout in Practice")).toBeInTheDocument();
    expect(within(card).getByText(/Ada Lovelace, Alan Turing · 2021 · p\. 4 · 4 Results/)).toBeInTheDocument();
    expect(within(card).getByText(/Verified excerpt/)).toBeInTheDocument();
    const link = within(card).getByRole("link", { name: /View in document/ });
    expect(link).toHaveAttribute("href", expect.stringContaining("/library/doc-1?page=4&chunk=chunk-1&start="));
  });

  it("keeps retrieval relevance, evidence strength and model confidence separate", () => {
    render(<EvidenceCard evidence={makeEvidence()} />);
    expect(screen.getByText("Evidence strength")).toBeInTheDocument();
    expect(screen.getByText("Retrieval relevance")).toBeInTheDocument();
    expect(screen.getByText("82% (uncalibrated)")).toBeInTheDocument();
  });

  it("never presents an unverified quotation as a quote", () => {
    const evidence = makeEvidence({}, { excerpt_verified: false, excerpt_text: null, excerpt_start: null, excerpt_end: null,
      issues: ["The model's quotation could not be found in the stored passage, so it is not shown."] });
    const { container } = render(<EvidenceCard evidence={evidence} />);
    expect(screen.queryByText(/Verified excerpt/)).toBeNull();
    expect(screen.getByText(/No quotation could be verified/)).toBeInTheDocument();
    expect(container.querySelector("blockquote")).toBeNull();
    expect(container.querySelector("mark")).toBeNull();
  });

  it("does not fabricate a citation when the source record is missing", () => {
    const evidence = makeEvidence({}, {
      valid: false, document_id: null, chunk_id: null, document_title: null, passage_text: null, reference: null,
      excerpt_text: null, excerpt_verified: false, page_start: null, page_label: null, authors: [], publication_year: null,
      issues: ["The source passage is no longer available (the document was deleted or reprocessed)."],
    });
    render(<EvidenceCard evidence={evidence} />);
    expect(screen.getByText("Source unavailable")).toBeInTheDocument();
    expect(screen.getByText("Citation could not be resolved.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /View in document/ })).toBeNull();
    expect(sourceHref(evidence)).toBeNull();
  });

  it("expands to the full stored passage", async () => {
    render(<EvidenceCard evidence={makeEvidence()} />);
    await userEvent.click(screen.getByRole("button", { name: /Show full passage/ }));
    expect(screen.getByText(/across all benchmarks/)).toBeInTheDocument();
  });
});

describe("EvidenceGroup", () => {
  it("shows the empty message when there is no evidence", () => {
    render(<EvidenceGroup title="Contradicting evidence" items={[]} empty="No passage contradicts the claim." />);
    expect(screen.getByText("No passage contradicts the claim.")).toBeInTheDocument();
  });
});

describe("VerdictPanel", () => {
  it("labels a model-written summary as AI-generated and shows the rule reasons", () => {
    render(
      <VerdictPanel
        verdict="MIXED_EVIDENCE"
        explanation="Sources disagree [P1] [P2]."
        explanationSource="model"
        reasons={["Decisive evidence points both ways (R5)."]}
        summary={{ retrieved_passages: 4, relevant_passages: 3, decisive_passages: 2, independent_sources: { supporting: 1, contradicting: 1, mixed: 0, all_relevant: 2 } }}
      />,
    );
    expect(screen.getByText(/AI-written summary/)).toBeInTheDocument();
    expect(screen.getByText(/R5/)).toBeInTheDocument();
    expect(screen.getByText("1 for · 1 against")).toBeInTheDocument();
  });

  it("labels the deterministic fallback as rule-based", () => {
    render(<VerdictPanel verdict="INCONCLUSIVE" explanation="Not enough evidence." explanationSource="template" reasons={[]} summary={{}} />);
    expect(screen.getByText("Rule-based summary")).toBeInTheDocument();
  });
});
