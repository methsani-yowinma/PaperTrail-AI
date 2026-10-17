"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, FileDown, Printer } from "lucide-react";

import { ErrorState } from "@/components/common/states";
import { EvidenceGroup } from "@/components/evidence/evidence-card";
import { VerdictPanel } from "@/components/evidence/verdict-panel";
import { Logo } from "@/components/layout/logo";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import type { Report } from "@/types/api";

export function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const report = useApi(() => api.getReport(id), [id]);

  if (report.error) return <ErrorState message={report.error.message} requestId={report.error.requestId} onRetry={report.reload} />;
  if (!report.data) return <Skeleton className="h-[32rem] rounded-xl" />;
  return <ReportDocument report={report.data} />;
}

function Section({ number, title, children }: { number: number; title: string; children: React.ReactNode }) {
  return (
    <section className="print-break-avoid space-y-3">
      <h2 className="text-lg font-semibold text-academic">
        <span className="mr-2 text-muted-foreground">{number}.</span>
        {title}
      </h2>
      {children}
    </section>
  );
}

export function ReportDocument({ report }: { report: Report }) {
  return (
    <div className="space-y-6">
      <div className="no-print flex flex-wrap items-center justify-between gap-3">
        <Link href="/reports" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" aria-hidden /> Evidence Reports
        </Link>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" asChild>
            <Link href={`/investigations/${report.investigation_id}`}>Open investigation</Link>
          </Button>
          <Button variant="outline" asChild>
            <a href={api.reportExportUrl(report.id, "markdown")} download>
              <FileDown /> Markdown
            </a>
          </Button>
          <Button variant="outline" asChild>
            <a href={api.reportExportUrl(report.id, "json")} download>
              <FileDown /> JSON
            </a>
          </Button>
          <Button onClick={() => window.print()}>
            <Printer /> Print / Save as PDF
          </Button>
        </div>
      </div>

      <article className="print-flat space-y-8 rounded-2xl border border-border bg-card p-6 sm:p-10">
        <header className="space-y-4 border-b border-border pb-6">
          <div className="flex items-center justify-between gap-4">
            <Logo />
            <span className="text-xs text-muted-foreground">Evidence report</span>
          </div>
          <Section number={1} title="Investigation">
            <p className="text-2xl font-semibold tracking-tight">{report.title}</p>
          </Section>
          <Section number={2} title="Submitted claim">
            <p className="text-[15px] leading-relaxed">{report.claim_text}</p>
            {report.research_context && <p className="text-sm text-muted-foreground">Research context: {report.research_context}</p>}
          </Section>
        </header>

        <Section number={3} title="Selected sources">
          <ol className="list-decimal space-y-1.5 pl-5 text-sm">
            {report.sources.map((s) => (
              <li key={s.document_id}>
                <span className="font-medium">{s.title || s.original_filename}</span>
                <span className="text-muted-foreground">
                  {" — "}
                  {[s.authors.length ? s.authors.join(", ") : "Authors not recorded", s.publication_year ?? "n.d.", s.page_count ? `${s.page_count} pages` : null]
                    .filter(Boolean)
                    .join(" · ")}
                  {s.doi && (
                    <>
                      {" · "}
                      <a href={`https://doi.org/${s.doi}`} className="text-primary hover:underline">doi:{s.doi}</a>
                    </>
                  )}
                </span>
              </li>
            ))}
          </ol>
        </Section>

        <Section number={4} title="Overall verdict">
          <VerdictPanel
            verdict={report.verdict}
            explanation={report.explanation}
            explanationSource={report.explanation_source}
            reasons={report.reasons}
            summary={report.evidence_summary}
          />
        </Section>

        <Section number={5} title="Supporting evidence">
          <EvidenceGroup title="Passages" items={report.supporting} empty="No passage supports the claim." printMode />
        </Section>
        <Section number={6} title="Contradicting evidence">
          <EvidenceGroup title="Passages" items={report.contradicting} empty="No passage contradicts the claim." printMode />
        </Section>
        <Section number={7} title="Mixed or inconclusive findings">
          <EvidenceGroup title="Mixed" items={report.mixed} empty="No passage reports mixed findings." printMode />
          {report.unassessed.length > 0 && <EvidenceGroup title="Not assessed" items={report.unassessed} printMode />}
          <p className="text-sm text-muted-foreground">
            {report.not_relevant.length} retrieved passage(s) were assessed as not relevant and are omitted from this report.
          </p>
        </Section>

        <Section number={8} title="Source metadata and page references">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 font-medium">Ref.</th>
                  <th className="py-2 pr-4 font-medium">Citation (from stored metadata)</th>
                  <th className="py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {[...report.supporting, ...report.contradicting, ...report.mixed, ...report.unassessed].map((e) => (
                  <tr key={e.id} className="border-b border-border align-top">
                    <td className="py-2 pr-4 font-mono text-xs">{e.label}</td>
                    <td className="py-2 pr-4">{e.citation.reference ?? "Unavailable"}</td>
                    <td className="py-2 text-xs">{e.citation.valid ? (e.citation.excerpt_verified ? "Verified excerpt" : "Passage verified") : "Unavailable"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <Section number={9} title="Methodology">
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {report.methodology.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </Section>

        <Section number={10} title="Limitations">
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {report.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </Section>

        <Section number={11} title="Assessment record">
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div><dt className="text-muted-foreground">Assessed</dt><dd>{formatDateTime(report.assessed_at)}</dd></div>
            <div><dt className="text-muted-foreground">Report generated</dt><dd>{formatDateTime(report.generated_at)}</dd></div>
            <div><dt className="text-muted-foreground">Model</dt><dd>{report.model_identifier ?? "None (no model call)"}</dd></div>
            <div><dt className="text-muted-foreground">Prompt / methodology</dt><dd>{report.prompt_version ?? "n/a"} / {report.methodology_version ?? "n/a"}</dd></div>
          </dl>
        </Section>
      </article>
    </div>
  );
}
