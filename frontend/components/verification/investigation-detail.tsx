"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { AlertTriangle, ArrowLeft, FileText, Loader2, Play, RotateCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ErrorState } from "@/components/common/states";
import { InvestigationStatusBadge, ProcessingBadge } from "@/components/common/status-badges";
import { EvidenceGroup } from "@/components/evidence/evidence-card";
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
import { documentTitle, formatAuthors, formatDateTime } from "@/lib/utils";
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
  if (!investigation.data) return <Skeleton className="h-96 rounded-xl" />;
  const inv = investigation.data;
  const busy = running || inv.status === "running";

  return (
    <div className="space-y-6">
      <Link href="/investigations" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" aria-hidden /> Investigations
      </Link>

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <InvestigationStatusBadge status={running ? "running" : inv.status} />
            <span className="text-xs text-muted-foreground">Created {formatDateTime(inv.created_at)}</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">{inv.title}</h1>
          {inv.title !== inv.claim_text && <p className="mt-2 text-[15px]"><span className="text-muted-foreground">Claim: </span>{inv.claim_text}</p>}
          {inv.research_context && <p className="mt-1 text-sm text-muted-foreground">Context: {inv.research_context}</p>}
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
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="min-w-0 space-y-6">
          {busy && (
            <div className="flex items-center gap-3 rounded-xl border border-primary/30 bg-primary/5 p-4 text-sm" aria-live="polite">
              <Loader2 className="size-5 animate-spin text-primary" aria-hidden />
              Retrieving passages, assessing each one and validating citations…
            </div>
          )}
          {!hasAssessment && !busy && (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                This investigation has not been verified yet. Select <strong>Verify now</strong> to retrieve and assess evidence.
              </CardContent>
            </Card>
          )}
          {inv.last_error && !busy && <ErrorState title="The last verification did not complete" message={inv.last_error} />}
          {evidence.error && <ErrorState message={evidence.error.message} onRetry={evidence.reload} />}
          {hasAssessment && !evidence.data && !evidence.error && <Skeleton className="h-64 rounded-xl" />}
          {evidence.data && <AssessmentResults assessment={evidence.data} />}
        </div>

        <aside className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Selected sources</CardTitle>
            </CardHeader>
            <CardContent>
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
              <CardHeader>
                <CardTitle>Reproducibility</CardTitle>
              </CardHeader>
              <CardContent>
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
      <dd className="text-right font-medium break-all">{value}</dd>
    </div>
  );
}

export function AssessmentResults({ assessment }: { assessment: Assessment }) {
  const by = (relation: string) => assessment.evidence.filter((e) => e.relation === relation);

  return (
    <div className="space-y-6">
      {assessment.status === "failed" ? (
        <div role="alert" className="rounded-xl border border-inconclusive/30 bg-inconclusive-soft p-5">
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
        <section className="rounded-xl border border-border bg-card p-5">
          <h3 className="font-semibold">Limitations</h3>
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
