"use client";

import Link from "next/link";
import { useState } from "react";
import { AlertTriangle, BookOpen, ChevronDown, ChevronUp, Link2Off, Sparkles } from "lucide-react";

import { RelationBadge } from "@/components/common/status-badges";
import { HighlightedPassage } from "@/components/evidence/highlighted-passage";
import { Badge } from "@/components/ui/badge";
import { cn, formatAuthors } from "@/lib/utils";
import { EVIDENCE_TYPE_LABELS, RELATIONS, titleCase } from "@/lib/verdict";
import type { Evidence } from "@/types/api";

export function sourceHref(e: Evidence): string | null {
  const c = e.citation;
  if (!c.valid || !c.document_id || !c.chunk_id || !c.page_start) return null;
  const params = new URLSearchParams({ page: String(c.page_start), chunk: c.chunk_id });
  if (c.excerpt_verified && c.excerpt_start != null && c.excerpt_end != null) {
    params.set("start", String(c.excerpt_start));
    params.set("end", String(c.excerpt_end));
  }
  return `/library/${c.document_id}?${params.toString()}`;
}

export function EvidenceCard({ evidence, printMode = false }: { evidence: Evidence; printMode?: boolean }) {
  const [expanded, setExpanded] = useState(printMode);
  const c = evidence.citation;
  const meta = RELATIONS[evidence.relation];
  const href = sourceHref(evidence);
  const pageText = c.page_label ? `p. ${c.page_label}` : null;

  return (
    <article className={cn("print-flat print-break-avoid rounded-xl border bg-card", meta.border)} aria-label={`Evidence ${evidence.label}`}>
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <span className="mt-0.5 rounded bg-muted px-1.5 py-0.5 font-mono text-xs font-semibold text-muted-foreground">{evidence.label}</span>
          <div className="min-w-0">
            {c.document_id ? (
              <p className="font-medium leading-snug">{c.document_title || c.original_filename}</p>
            ) : (
              <p className="inline-flex items-center gap-1.5 font-medium text-muted-foreground">
                <Link2Off className="size-4" aria-hidden /> Source unavailable
              </p>
            )}
            <p className="mt-0.5 text-sm text-muted-foreground">
              {[formatAuthors(c.authors, 2), c.publication_year, pageText, c.section_title].filter(Boolean).join(" · ")}
            </p>
          </div>
        </div>
        <RelationBadge relation={evidence.relation} />
      </header>

      <div className="space-y-3 px-4 py-3">
        {c.excerpt_text ? (
          <blockquote className="border-l-2 border-primary/40 pl-3">
            <p className="prose-excerpt">&ldquo;{c.excerpt_text}&rdquo;</p>
            <p className="mt-1 text-xs text-muted-foreground">Verified excerpt: matches the stored passage text.</p>
          </blockquote>
        ) : c.passage_text ? (
          <p className="text-xs text-muted-foreground">No quotation could be verified for this passage; the stored passage text is shown below.</p>
        ) : null}

        {c.passage_text && (
          <div>
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="no-print inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
              aria-expanded={expanded}
            >
              {expanded ? <ChevronUp className="size-4" aria-hidden /> : <ChevronDown className="size-4" aria-hidden />}
              {expanded ? "Hide full passage" : "Show full passage"}
            </button>
            {(expanded || !c.excerpt_text) && (
              <div className="mt-2 rounded-lg bg-muted/50 p-3">
                <HighlightedPassage text={c.passage_text} start={c.excerpt_start} end={c.excerpt_end} />
              </div>
            )}
          </div>
        )}

        {evidence.rationale && (
          <div className="rounded-lg border border-ai/20 bg-mixed-soft/60 p-3">
            <p className="mb-1 inline-flex items-center gap-1 text-xs font-semibold text-ai">
              <Sparkles className="size-3.5" aria-hidden /> Model assessment
            </p>
            <p className="text-sm leading-relaxed">{evidence.rationale}</p>
            {evidence.limitations.length > 0 && (
              <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">
                {evidence.limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-4">
          <Metric label="Evidence strength" value={titleCase(evidence.evidence_strength)} hint="Model judgement of how strongly this passage bears on the claim." />
          <Metric label="Directness" value={titleCase(evidence.directness)} hint="Direct evidence concerns the claim's exact subject and conditions." />
          <Metric label="Evidence type" value={evidence.evidence_type ? EVIDENCE_TYPE_LABELS[evidence.evidence_type] : "—"} />
          <Metric
            label="Model confidence"
            value={evidence.model_confidence != null ? `${Math.round(evidence.model_confidence * 100)}% (uncalibrated)` : "—"}
            hint="Self-reported by the model about its label. Not used for the verdict."
          />
          <Metric
            label="Retrieval relevance"
            value={`#${evidence.retrieval.rank} · ${evidence.retrieval.method}`}
            hint={`Fused rank score ${evidence.retrieval.fused_score.toFixed(4)}${
              evidence.retrieval.semantic_similarity != null ? `, cosine similarity ${evidence.retrieval.semantic_similarity.toFixed(2)}` : ""
            }. Measures topical match, not truth.`}
          />
        </dl>

        {c.issues.length > 0 && (
          <ul className="space-y-1">
            {c.issues.map((issue) => (
              <li key={issue} className="flex gap-1.5 text-xs text-inconclusive">
                <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden /> {issue}
              </li>
            ))}
          </ul>
        )}
      </div>

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-2.5">
        <p className="min-w-0 text-xs text-muted-foreground">{c.reference ?? "Citation could not be resolved."}</p>
        {href && !printMode && (
          <Link href={href} className="no-print inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
            <BookOpen className="size-4" aria-hidden /> View in document
          </Link>
        )}
      </footer>
    </article>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div title={hint}>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

export function EvidenceGroup({
  title,
  items,
  empty,
  collapsedByDefault = false,
  printMode = false,
}: {
  title: string;
  items: Evidence[];
  empty?: string;
  collapsedByDefault?: boolean;
  printMode?: boolean;
}) {
  const [open, setOpen] = useState(!collapsedByDefault || printMode);
  if (!items.length && !empty) return null;
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold">
          {title} <Badge className="ml-1 align-middle">{items.length}</Badge>
        </h3>
        {collapsedByDefault && items.length > 0 && !printMode && (
          <button type="button" className="no-print text-sm text-primary hover:underline" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
            {open ? "Hide" : "Show"}
          </button>
        )}
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        open && (
          <div className="space-y-3">
            {items.map((e) => (
              <EvidenceCard key={e.id} evidence={e} printMode={printMode} />
            ))}
          </div>
        )
      )}
    </section>
  );
}
