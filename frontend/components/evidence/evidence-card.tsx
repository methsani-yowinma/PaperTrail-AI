"use client";

import Link from "next/link";
import { useState } from "react";
import { AlertTriangle, BadgeCheck, BookOpen, ChevronDown, ChevronUp, Link2Off, Quote, Sparkles } from "lucide-react";

import { RelationBadge } from "@/components/common/status-badges";
import { HighlightedPassage } from "@/components/evidence/highlighted-passage";
import { cn, formatAuthors } from "@/lib/utils";
import { EVIDENCE_TYPE_LABELS, RELATIONS, titleCase } from "@/lib/verdict";
import type { Evidence, PassageRelation } from "@/types/api";

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

/** Thin vertical rule on each card, coloured by relation. Always paired with the text badge. */
export const RELATION_RULE: Record<PassageRelation, string> = {
  SUPPORTS: "bg-supported",
  CONTRADICTS: "bg-contradicted",
  MIXED: "bg-mixed",
  NOT_RELEVANT: "bg-border",
  UNASSESSED: "bg-border",
};

export function EvidenceCard({ evidence, printMode = false }: { evidence: Evidence; printMode?: boolean }) {
  const [expanded, setExpanded] = useState(printMode);
  const c = evidence.citation;
  const meta = RELATIONS[evidence.relation];
  const href = sourceHref(evidence);
  const pageText = c.page_label ? `p. ${c.page_label}` : null;
  const similarity = evidence.retrieval.semantic_similarity;

  return (
    <article
      id={`evidence-${evidence.label}`}
      className={cn(
        "@container print-flat print-break-avoid relative scroll-mt-20 overflow-hidden rounded-lg border bg-card shadow-panel transition-shadow duration-200 hover:shadow-raised",
        meta.border,
      )}
      aria-label={`Evidence ${evidence.label}`}
    >
      <span aria-hidden className={cn("absolute inset-y-0 left-0 w-[3px]", RELATION_RULE[evidence.relation])} />
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-rule py-3 pr-4 pl-5">
        <div className="flex min-w-0 items-start gap-3">
          <span className="mt-0.5 rounded-[4px] border border-border bg-muted px-1.5 py-0.5 font-mono text-[11px] font-semibold text-academic">
            {evidence.label}
          </span>
          <div className="min-w-0">
            {c.document_id ? (
              <p className="leading-snug font-semibold text-foreground">{c.document_title || c.original_filename}</p>
            ) : (
              <p className="inline-flex items-center gap-1.5 font-medium text-muted-foreground">
                <Link2Off className="size-4" aria-hidden /> Source unavailable
              </p>
            )}
            <p className="mt-0.5 text-[13px] text-muted-foreground">
              {[formatAuthors(c.authors, 2), c.publication_year, pageText, c.section_title].filter(Boolean).join(" · ")}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {c.page_label && (
            <span className="rounded-[4px] border border-border px-1.5 py-0.5 font-mono text-[11px] text-academic" title="Cited page">
              <span className="text-muted-foreground">PAGE </span>
              {c.page_label}
            </span>
          )}
          <RelationBadge relation={evidence.relation} />
        </div>
      </header>

      <div className="space-y-4 py-4 pr-4 pl-5">
        {c.excerpt_text ? (
          <figure>
            <figcaption className="eyebrow mb-1.5 inline-flex items-center gap-1.5 text-academic">
              <Quote className="size-3.5" aria-hidden /> Source text · verified
            </figcaption>
            <blockquote className="border-l-2 border-academic pl-3.5">
              <p className="prose-excerpt text-[15.5px]">&ldquo;{c.excerpt_text}&rdquo;</p>
            </blockquote>
            <p className="mt-1.5 inline-flex items-center gap-1 text-xs text-muted-foreground">
              <BadgeCheck className="size-3.5 text-academic" aria-hidden /> Verified excerpt: matches the stored passage text.
            </p>
          </figure>
        ) : c.passage_text ? (
          <p className="text-xs text-muted-foreground">No quotation could be verified for this passage; the stored passage text is shown below.</p>
        ) : null}

        {c.passage_text && (
          <div>
            {c.excerpt_text && (
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="no-print inline-flex items-center gap-1 rounded-sm text-[13px] font-medium text-primary hover:underline"
                aria-expanded={expanded}
              >
                {expanded ? <ChevronUp className="size-4" aria-hidden /> : <ChevronDown className="size-4" aria-hidden />}
                {expanded ? "Hide full passage" : "Show full passage"}
              </button>
            )}
            {(expanded || !c.excerpt_text) && (
              <div className="mt-2 rounded-md border first:mt-0 border-rule bg-muted/40 p-3.5">
                <p className="eyebrow mb-1.5">Stored passage{pageText ? ` · ${pageText}` : ""}</p>
                <HighlightedPassage text={c.passage_text} start={c.excerpt_start} end={c.excerpt_end} />
              </div>
            )}
          </div>
        )}

        {evidence.rationale && (
          <div className="rounded-md border border-dashed border-ai/35 bg-mixed-soft/40 p-3.5">
            <p className="eyebrow mb-1.5 inline-flex items-center gap-1.5 text-ai">
              <Sparkles className="size-3.5" aria-hidden /> AI assessment · model-generated, not a source
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

        {evidence.relation === "UNASSESSED" ? (
          <p className="font-mono text-[11.5px] text-muted-foreground" title="Measures topical match, not truth.">
            Retrieval relevance: #{evidence.retrieval.rank} · {evidence.retrieval.method}
            {similarity != null ? ` · cos ${similarity.toFixed(2)}` : ""} · not assessed by the model
          </p>
        ) : (
          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-rule bg-rule text-xs @md:grid-cols-3 @2xl:grid-cols-5">
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
              // Five metrics: span the leftover cell in the 2- and 3-column layouts so no empty cell shows.
              className="col-span-2 @2xl:col-span-1"
              value={`#${evidence.retrieval.rank} · ${evidence.retrieval.method}`}
              detail={similarity != null ? `cos ${similarity.toFixed(2)}` : undefined}
              hint={`Fused rank score ${evidence.retrieval.fused_score.toFixed(4)}${
                similarity != null ? `, cosine similarity ${similarity.toFixed(2)}` : ""
              }. Measures topical match, not truth.`}
            />
          </dl>
        )}

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

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-rule bg-muted/30 py-2.5 pr-4 pl-5">
        <p className="min-w-0 font-mono text-[11.5px] leading-relaxed text-muted-foreground">{c.reference ?? "Citation could not be resolved."}</p>
        {href && !printMode && (
          <Link href={href} className="no-print inline-flex items-center gap-1 rounded-sm text-[13px] font-medium text-primary hover:underline">
            <BookOpen className="size-4" aria-hidden /> View in document
          </Link>
        )}
      </footer>
    </article>
  );
}

function Metric({ label, value, hint, detail, className }: { label: string; value: string; hint?: string; detail?: string; className?: string }) {
  return (
    <div title={hint} className={cn("bg-card px-3 py-2", className)}>
      <dt className="eyebrow text-[10px]">{label}</dt>
      <dd className="mt-0.5 font-medium text-foreground">
        {value}
        {detail && <span className="ml-1.5 font-mono text-[11px] font-normal text-muted-foreground">{detail}</span>}
      </dd>
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
    <section className="space-y-3" aria-label={title}>
      <div className="flex items-center justify-between border-b border-border pb-2">
        <h3 className="flex items-center gap-2 text-[15px] font-semibold tracking-tight text-academic">
          {title}
          <span className="tabular rounded-[4px] border border-border bg-card px-1.5 font-mono text-[11px] font-medium text-muted-foreground">
            {items.length}
          </span>
        </h3>
        {collapsedByDefault && items.length > 0 && !printMode && (
          <button type="button" className="no-print rounded-sm text-[13px] text-primary hover:underline" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
            {open ? "Hide" : "Show"}
          </button>
        )}
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        open && (
          <div className="space-y-4">
            {items.map((e) => (
              <EvidenceCard key={e.id} evidence={e} printMode={printMode} />
            ))}
          </div>
        )
      )}
    </section>
  );
}
