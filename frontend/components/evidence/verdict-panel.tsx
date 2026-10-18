import { Info, ListChecks, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import { VERDICTS } from "@/lib/verdict";
import type { EvidenceSummary, Verdict } from "@/types/api";

const VERDICT_RULE: Record<Verdict, string> = {
  SUPPORTED: "bg-supported",
  CONTRADICTED: "bg-contradicted",
  MIXED_EVIDENCE: "bg-mixed",
  INCONCLUSIVE: "bg-inconclusive",
};

export function VerdictPanel({
  verdict,
  explanation,
  explanationSource,
  reasons,
  summary,
}: {
  verdict: Verdict;
  explanation: string | null;
  explanationSource: "model" | "template" | null;
  reasons: string[];
  summary: EvidenceSummary;
}) {
  const meta = VERDICTS[verdict];
  const Icon = meta.icon;
  const sources = summary.independent_sources;
  return (
    <section aria-label="Overall verdict" className={cn("print-flat relative overflow-hidden rounded-lg border bg-card shadow-panel", meta.border)}>
      <span aria-hidden className={cn("absolute inset-y-0 left-0 w-1", VERDICT_RULE[verdict])} />

      <div className={cn("flex flex-col gap-4 py-5 pr-5 pl-6 sm:flex-row sm:items-start sm:pr-6", meta.soft)}>
        <span className={cn("flex size-12 shrink-0 items-center justify-center rounded-md border bg-card", meta.border, meta.text)}>
          <Icon className="size-6" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="eyebrow">Finding · within the selected documents</p>
          <h2 className={cn("mt-1 text-2xl font-semibold tracking-tight", meta.text)}>{meta.label}</h2>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-foreground/80">{meta.description}</p>
        </div>
      </div>

      {summary.retrieved_passages !== undefined && (
        <dl className="grid grid-cols-2 gap-px border-y border-rule bg-rule sm:grid-cols-4">
          <SummaryStat label="Passages retrieved" value={summary.retrieved_passages} />
          <SummaryStat label="Relevant passages" value={summary.relevant_passages} />
          <SummaryStat label="Decisive passages" value={summary.decisive_passages} hint="Direct, moderate-or-strong, and not background or cited prior work." />
          <SummaryStat
            label="Independent sources"
            value={sources ? `${sources.supporting} for · ${sources.contradicting} against` : undefined}
            hint="Documents sharing a DOI count once."
          />
        </dl>
      )}

      {(reasons.length > 0 || explanation) && (
        <div className="grid gap-px bg-rule md:grid-cols-2">
          {reasons.length > 0 && (
            <div className="bg-card px-6 py-4">
              <p className="eyebrow inline-flex items-center gap-1.5 text-academic">
                <ListChecks className="size-3.5" aria-hidden /> Why this verdict · deterministic rules
              </p>
              <ul className="mt-2 space-y-1.5 text-sm leading-relaxed">
                {reasons.map((r) => (
                  <li key={r} className="flex gap-2">
                    <span aria-hidden className="mt-2 size-1 shrink-0 rounded-full bg-academic" />
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {explanation && (
            <div className={cn("bg-card px-6 py-4", !reasons.length && "md:col-span-2")}>
              <p className={cn("eyebrow inline-flex items-center gap-1.5", explanationSource === "model" && "text-ai")}>
                {explanationSource === "model" ? (
                  <>
                    <Sparkles className="size-3.5" aria-hidden /> AI-written summary of the validated assessments
                  </>
                ) : (
                  <>
                    <Info className="size-3.5" aria-hidden /> Rule-based summary
                  </>
                )}
              </p>
              <p
                className={cn(
                  "mt-2 text-[14.5px] leading-relaxed",
                  explanationSource === "model" && "rounded-md border border-dashed border-ai/35 bg-mixed-soft/30 p-3",
                )}
              >
                {explanation}
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function SummaryStat({ label, value, hint }: { label: string; value: number | string | undefined; hint?: string }) {
  return (
    <div className="bg-card px-5 py-3" title={hint}>
      <dt className="eyebrow text-[10px]">{label}</dt>
      <dd className="tabular mt-0.5 font-mono text-lg font-semibold text-academic">{value ?? "—"}</dd>
    </div>
  );
}

export function MeasuresLegend() {
  const items = [
    ["Retrieval relevance", "How well a passage matched the claim's wording and meaning. It decides what is read, not what is true."],
    ["Evidence strength", "The model's judgement of how strongly a passage bears on the claim (strong, moderate or weak)."],
    ["Model confidence", "The model's self-reported certainty about its label. Uncalibrated, and never used for the verdict."],
    ["Overall verdict", "Computed by documented, deterministic rules from validated passage assessments and independent sources."],
  ];
  return (
    <details className="no-print group rounded-lg border border-border bg-card text-sm shadow-panel">
      <summary className="flex cursor-pointer items-center justify-between rounded-lg px-4 py-3 font-medium select-none">
        How to read these results
        <span className="eyebrow group-open:hidden">Show</span>
        <span className="eyebrow hidden group-open:inline">Hide</span>
      </summary>
      <dl className="grid gap-x-6 gap-y-3 border-t border-rule px-4 py-3 sm:grid-cols-2">
        {items.map(([term, text]) => (
          <div key={term}>
            <dt className="font-medium">{term}</dt>
            <dd className="text-muted-foreground">{text}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
