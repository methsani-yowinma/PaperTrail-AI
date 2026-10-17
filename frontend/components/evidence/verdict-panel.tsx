import { Info, Sparkles } from "lucide-react";

import { VerdictBadge } from "@/components/common/status-badges";
import { cn } from "@/lib/utils";
import { VERDICTS } from "@/lib/verdict";
import type { EvidenceSummary, Verdict } from "@/types/api";

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
  const sources = summary.independent_sources;
  return (
    <section aria-label="Overall verdict" className={cn("print-flat rounded-2xl border p-5 sm:p-6", meta.border, meta.soft)}>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm font-medium text-muted-foreground">Overall verdict</span>
        <VerdictBadge verdict={verdict} size="lg" />
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{meta.description}</p>

      {explanation && (
        <div className="mt-4 rounded-xl bg-card/80 p-4">
          <p className="mb-1.5 inline-flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
            {explanationSource === "model" ? (
              <>
                <Sparkles className="size-3.5 text-ai" aria-hidden /> AI-written summary of the validated assessments
              </>
            ) : (
              <>
                <Info className="size-3.5" aria-hidden /> Rule-based summary
              </>
            )}
          </p>
          <p className="text-[15px] leading-relaxed">{explanation}</p>
        </div>
      )}

      {reasons.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Why this verdict</p>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm">
            {reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {summary.retrieved_passages !== undefined && (
        <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
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
    </section>
  );
}

function SummaryStat({ label, value, hint }: { label: string; value: number | string | undefined; hint?: string }) {
  return (
    <div className="rounded-lg bg-card/80 px-3 py-2" title={hint}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-lg font-semibold">{value ?? "—"}</dd>
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
    <details className="no-print rounded-xl border border-border bg-card p-4 text-sm">
      <summary className="cursor-pointer font-medium">How to read these results</summary>
      <dl className="mt-3 grid gap-3 sm:grid-cols-2">
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
