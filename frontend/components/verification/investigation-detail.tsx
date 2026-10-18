"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { AlertTriangle, ArrowLeft, FileText, Loader2, Play, RotateCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ErrorState } from "@/components/common/states";
import { InvestigationStatusBadge, ProcessingBadge } from "@/components/common/status-badges";
import { EvidenceGroup, RELATION_RULE } from "@/components/evidence/evidence-card";
import { MeasuresLegend, VerdictPanel } from "@/components/evidence/verdict-panel";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { ApiError, api } from "@/lib/api";
import { cn, documentTitle, formatAuthors, formatDateTime } from "@/lib/utils";
import { RELATIONS } from "@/lib/verdict";
import type { Assessment } from "@/types/api";

export function InvestigationDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [running, setRunning] = useState(false);
  const investigation = useApi(() => api.getInvestigation(id), [id], {
    pollMs: 3000,
    pollWhile: (inv) => inv.status === "running",
  });
  const hasAssessment = Boolean(investigation.data?.latest_assessment);
  const evidence = useApi(() => api.latestEvidence(id), [id, investigation.data?.latest_assessment?.id], { enabled: hasAssessment });

  async function runVerification() {
    setRunning(true);
    try {
      const result = await api.verifyInvestigation(id);
      investigation.setData(result.investigation);
      evidence.setData(result.assessment);
      if (result.assessment.status === "failed") toast.warning("Evidence retrieved, but assessment failed.");
      else toast.success("Verification complete");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Verification failed.");
      void investigation.reload();
    } finally {
      setRunning(false);
    }
  }

  async function remove() {
    try {
      await api.deleteInvestigation(id);
      toast.success("Investigation deleted");
      router.replace("/investigations");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not delete the investigation.");
    }
  }

  if (investigation.error) return <ErrorState message={investigation.error.message} requestId={investigation.error.requestId} onRetry={investigation.reload} />;
  if (!investigation.data) return <Skeleton className="h-96 rounded-lg" />;
  const inv = investigation.data;
  const busy = running || inv.status === "running";

  return (
    <div className="space-y-6">
      <Link href="/investigations" className="inline-flex items-center gap-1 rounded-sm text-[13px] text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" aria-hidden /> Investigations
      </Link>

      <header className="flex flex-col gap-5 border-b border-border pb-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="eyebrow text-primary">Investigation</span>
            <InvestigationStatusBadge status={running ? "running" : inv.status} />
            <span className="font-mono text-[11px] text-muted-foreground">Created {formatDateTime(inv.created_at)}</span>
          </div>
          <h1 className="text-[26px] leading-tight font-semibold tracking-tight text-academic">{inv.title}</h1>
          {inv.title !== inv.claim_text && (
            <div className="mt-4 max-w-3xl rounded-md border border-border border-l-[3px] border-l-academic bg-card px-4 py-3 shadow-panel">
              <p className="eyebrow">Claim under examination</p>
              <p className="mt-1 text-[15.5px] leading-relaxed">{inv.claim_text}</p>
            </div>
          )}
          {inv.research_context && (
            <p className="mt-3 text-sm text-muted-foreground">
              <span className="eyebrow mr-2">Context</span>
              {inv.research_context}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {evidence.data?.status === "completed" && (
            <Button asChild variant="outline">
              <Link href={`/reports/${evidence.data.id}`}>
                <FileText /> Evidence report
              </Link>
            </Button>
          )}
          <Button onClick={runVerification} disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : hasAssessment ? <RotateCw /> : <Play />}
            {busy ? "Verifying…" : hasAssessment ? "Run again" : "Verify now"}
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" className="text-contradicted hover:bg-contradicted-soft" disabled={busy}>
                <Trash2 /> Delete
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete this investigation?</AlertDialogTitle>
                <AlertDialogDescription>
                  The investigation and all of its assessments and reports will be permanently deleted. Your documents are not affected.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={remove}>Delete investigation</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </header>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 space-y-6">
          {busy && (
            <div className="flex items-center gap-3 rounded-lg border border-primary/30 bg-primary/5 p-4 text-sm" aria-live="polite">
              <Loader2 className="size-5 animate-spin text-primary" aria-hidden />
              Retrieving passages, assessing each one and validating citations…
            </div>
          )}
          {!hasAssessment && !busy && (
            <div className="bg-graph rounded-lg border border-dashed border-primary/25 px-6 py-12 text-center text-sm text-muted-foreground">
              This investigation has not been verified yet. Select <strong className="text-foreground">Verify now</strong> to retrieve and assess evidence.
            </div>
          )}
          {/* A failed assessment already explains its own error below; don't repeat it. */}
          {inv.last_error && !busy && inv.last_error !== evidence.data?.error_message && (
            <ErrorState title="The last verification did not complete" message={inv.last_error} />
          )}
          {evidence.error && <ErrorState message={evidence.error.message} onRetry={evidence.reload} />}
          {hasAssessment && !evidence.data && !evidence.error && <Skeleton className="h-64 rounded-lg" />}
          {evidence.data && <AssessmentResults assessment={evidence.data} />}
        </div>

        <aside className="min-w-0 space-y-5 lg:sticky lg:top-16 lg:self-start">
          {evidence.data && evidence.data.evidence.length > 0 && <EvidenceIndex assessment={evidence.data} />}
          <Card>
            <CardHeader className="border-b border-rule">
              <CardTitle>Selected sources</CardTitle>
            </CardHeader>
            <CardContent className="pt-3">
              <ul className="space-y-3">
                {inv.documents.map((d) => (
                  <li key={d.id} className="text-sm">
                    <Link href={`/library/${d.id}`} className="font-medium hover:text-primary hover:underline">
                      {documentTitle(d)}
                    </Link>
                    <p className="text-xs text-muted-foreground">{[formatAuthors(d.authors, 2), d.publication_year].filter(Boolean).join(" · ") || d.original_filename}</p>
                    {d.processing_status !== "completed" && <div className="mt-1"><ProcessingBadge status={d.processing_status} /></div>}
                  </li>
                ))}
              </ul>
              {inv.missing_document_count > 0 && (
                <p className="mt-3 text-xs text-inconclusive">{inv.missing_document_count} selected document(s) were deleted.</p>
              )}
            </CardContent>
          </Card>
          {evidence.data && (
            <Card>
              <CardHeader className="border-b border-rule">
                <CardTitle>Reproducibility</CardTitle>
              </CardHeader>
              <CardContent className="pt-3">
                <dl className="space-y-2 text-xs">
                  <Row label="Assessed" value={formatDateTime(evidence.data.created_at)} />
                  <Row label="Model" value={evidence.data.model_identifier ?? "None (no model call)"} />
                  <Row label="Prompt version" value={evidence.data.prompt_version ?? "—"} />
                  <Row label="Methodology" value={evidence.data.methodology_version ?? inv.methodology_version} />
                  <Row label="Embedding model" value={String(evidence.data.retrieval_configuration.embedding_model ?? "—")} />
                  <Row label="Passages requested" value={String(evidence.data.retrieval_configuration.top_k ?? "—")} />
                  <Row label="Model calls" value={String(evidence.data.metadata.llm_calls ?? 0)} />
                </dl>
              </CardContent>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-mono text-[11.5px] font-medium break-all">{value}</dd>
    </div>
  );
}

/** Jump list of every retrieved passage: label, relation, source and page, all from stored records. */
function EvidenceIndex({ assessment }: { assessment: Assessment }) {
  // Not-relevant passages are collapsed by default, so they are not linked from the index.
  const items = assessment.evidence.filter((e) => assessment.status === "failed" || e.relation !== "NOT_RELEVANT");
  const hidden = assessment.evidence.length - items.length;
  return (
    <nav aria-label="Evidence index" className="rounded-lg border border-border bg-card shadow-panel">
      <p className="eyebrow border-b border-rule px-4 py-3 text-academic">Evidence index</p>
      <ol className="max-h-[22rem] divide-y divide-rule overflow-y-auto">
        {items.map((e) => {
          const meta = RELATIONS[e.relation];
          const Icon = meta.icon;
          return (
            <li key={e.id}>
              <a href={`#evidence-${e.label}`} className="relative flex items-start gap-2.5 py-2.5 pr-3 pl-4 text-xs hover:bg-muted/50">
                <span aria-hidden className={cn("absolute inset-y-2 left-0 w-[2px] rounded-full", RELATION_RULE[e.relation])} />
                <span className="mt-px font-mono text-[11px] font-semibold text-academic">{e.label}</span>
                <span className="min-w-0 flex-1">
                  <span className={cn("inline-flex items-center gap-1 font-semibold", meta.text)}>
                    <Icon className="size-3.5" aria-hidden /> {meta.label}
                  </span>
                  <span className="block truncate text-muted-foreground">
                    {e.citation.document_title || e.citation.original_filename || "Source unavailable"}
                  </span>
                </span>
                {e.citation.page_label && <span className="mt-px shrink-0 font-mono text-[11px] text-muted-foreground">p. {e.citation.page_label}</span>}
              </a>
            </li>
          );
        })}
      </ol>
      {hidden > 0 && <p className="border-t border-rule px-4 py-2 text-[11px] text-muted-foreground">{hidden} not-relevant passage(s) listed in the results.</p>}
    </nav>
  );
}

export function AssessmentResults({ assessment }: { assessment: Assessment }) {
  const by = (relation: string) => assessment.evidence.filter((e) => e.relation === relation);

  return (
    <div className="space-y-7">
      {assessment.status === "failed" ? (
        <div role="alert" className="rounded-lg border border-inconclusive/30 border-l-4 border-l-inconclusive bg-inconclusive-soft p-5">
          <p className="flex items-center gap-2 font-semibold text-inconclusive">
            <AlertTriangle className="size-5" aria-hidden /> No verdict: the evidence could not be assessed
          </p>
          <p className="mt-1 text-sm">{assessment.error_message}</p>
          <p className="mt-1 text-sm text-muted-foreground">The passages below were retrieved but have not been assessed.</p>
        </div>
      ) : (
        assessment.verdict && (
          <VerdictPanel
            verdict={assessment.verdict}
            explanation={assessment.explanation}
            explanationSource={assessment.explanation_source}
            reasons={assessment.reasons}
            summary={assessment.evidence_summary}
          />
        )
      )}

      <MeasuresLegend />

      {assessment.status === "completed" && (
        <>
          <EvidenceGroup title="Supporting evidence" items={by("SUPPORTS")} empty="No passage supports the claim." />
          <EvidenceGroup title="Contradicting evidence" items={by("CONTRADICTS")} empty="No passage contradicts the claim." />
          <EvidenceGroup title="Mixed findings" items={by("MIXED")} />
          <EvidenceGroup title="Not assessed" items={by("UNASSESSED")} />
          <EvidenceGroup title="Retrieved but not relevant" items={by("NOT_RELEVANT")} collapsedByDefault />
        </>
      )}
      {assessment.status === "failed" && <EvidenceGroup title="Retrieved passages" items={assessment.evidence} />}

      {assessment.limitations.length > 0 && (
        <section className="rounded-lg border border-border bg-card p-5 shadow-panel">
          <h3 className="eyebrow text-academic">Limitations</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {assessment.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
            <li>This result reflects only the selected documents and does not establish scientific truth.</li>
          </ul>
        </section>
      )}
    </div>
  );
}
