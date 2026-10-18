"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertTriangle, CheckCircle2, Circle, FileSearch, Loader2, Search, Upload } from "lucide-react";
import { toast } from "sonner";

import { EmptyState, ErrorState, PageHeader } from "@/components/common/states";
import { ProcessingBadge } from "@/components/common/status-badges";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useApi } from "@/hooks/use-api";
import { ApiError, api } from "@/lib/api";
import { cn, documentTitle, formatAuthors } from "@/lib/utils";

export const verifySchema = z.object({
  claim_text: z
    .string()
    .trim()
    .min(5, "Write a claim or question of at least 5 characters.")
    .max(2000, "Keep the claim under 2,000 characters."),
  title: z.string().trim().max(200, "Keep the title under 200 characters."),
  research_context: z.string().trim().max(4000, "Keep the context under 4,000 characters."),
  document_ids: z
    .array(z.string())
    .min(1, "Select at least one processed document.")
    .max(50, "Select at most 50 documents per investigation."),
  top_k: z.number().int().min(3).max(20),
});
export type VerifyValues = z.infer<typeof verifySchema>;

type Phase = "idle" | "creating" | "verifying";

export function VerifyForm() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<ApiError | null>(null);
  const [filter, setFilter] = useState("");
  const docs = useApi(() => api.listDocuments({ limit: 100 }), []);
  const system = useApi(() => api.systemStatus(), []);

  const form = useForm<VerifyValues>({
    resolver: zodResolver(verifySchema),
    defaultValues: { claim_text: "", title: "", research_context: "", document_ids: [], top_k: 8 },
  });

  const selectedIds = useWatch({ control: form.control, name: "document_ids" });
  const claimText = useWatch({ control: form.control, name: "claim_text" });
  const topK = useWatch({ control: form.control, name: "top_k" });
  const usable = docs.data?.items.filter((d) => d.processing_status === "completed") ?? [];
  const unusable = docs.data?.items.filter((d) => d.processing_status !== "completed") ?? [];
  const needle = filter.trim().toLowerCase();
  const matches = (d: (typeof usable)[number]) =>
    !needle || [documentTitle(d), d.original_filename, ...d.authors].some((v) => v.toLowerCase().includes(needle));
  const visibleUsable = usable.filter(matches);

  async function onSubmit(values: VerifyValues) {
    setError(null);
    setPhase("creating");
    let investigationId: string | null = null;
    try {
      const investigation = await api.createInvestigation({
        claim_text: values.claim_text,
        title: values.title || undefined,
        research_context: values.research_context || undefined,
        document_ids: values.document_ids,
        settings: { top_k: values.top_k },
      });
      investigationId = investigation.id;
      setPhase("verifying");
      const result = await api.verifyInvestigation(investigation.id);
      if (result.assessment.status === "failed") {
        toast.warning("Evidence was retrieved but could not be assessed.", { description: result.assessment.error_message ?? undefined });
      } else {
        toast.success("Verification complete");
      }
      router.push(`/investigations/${investigation.id}`);
    } catch (err) {
      setPhase("idle");
      const apiError = err instanceof ApiError ? err : new ApiError("Verification failed.", 0, "unknown");
      setError(apiError);
      if (investigationId) {
        toast.error("Verification failed. The investigation was saved and can be retried.", {
          action: { label: "Open", onClick: () => router.push(`/investigations/${investigationId}`) },
        });
      }
    }
  }

  const { errors } = form.formState;
  const busy = phase !== "idle";
  const assessmentConfigured = system.data?.assessment_configured;

  return (
    <>
      <PageHeader
        eyebrow="Verification workspace"
        title="Verify a claim"
        description="State a claim or research question, choose the documents to search, and PaperTrail AI will retrieve and assess the relevant evidence. Only your selected documents are searched, not the internet."
      />

      {system.data && !assessmentConfigured && (
        <div role="note" className="mb-6 flex gap-3 rounded-lg border border-inconclusive/30 border-l-[3px] border-l-inconclusive bg-inconclusive-soft p-4 text-sm">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-inconclusive" aria-hidden />
          <p>
            <strong>Claim assessment is not configured.</strong> Retrieval will still run and you will see the relevant
            passages, but no verdict will be produced until <code className="font-mono text-xs">GOOGLE_API_KEY</code> and{" "}
            <code className="font-mono text-xs">GEMINI_MODEL</code> are set on the backend. See <Link href="/settings" className="text-primary underline">Settings</Link>.
          </p>
        </div>
      )}

      <form
        onSubmit={form.handleSubmit(onSubmit)}
        noValidate
        className="grid grid-cols-[minmax(0,1fr)] items-start gap-5 lg:grid-cols-[minmax(0,1fr)_290px] xl:grid-cols-[270px_minmax(0,1fr)_270px]"
      >
        {/* 01 — Corpus */}
        <section aria-labelledby="corpus-heading" className="pane xl:col-start-1 xl:row-start-1">
          <PaneHeader
            index="01"
            label="Corpus"
            title="Documents to search"
            id="corpus-heading"
            aside={
              docs.data && (
                <span className="tabular font-mono text-[11px] text-muted-foreground">
                  {selectedIds.length} / {usable.length} selected
                </span>
              )
            }
          />
          <div className="space-y-3 p-4">
            {docs.error && <ErrorState message={docs.error.message} onRetry={docs.reload} />}
            {docs.loading && !docs.data && <Skeleton className="h-32" />}
            {docs.data && docs.data.items.length === 0 && (
              <EmptyState
                icon={Upload}
                title="No documents yet"
                description="Upload research papers to your library before verifying a claim."
                action={
                  <Button asChild variant="outline">
                    <Link href="/library">Go to Research Library</Link>
                  </Button>
                }
              />
            )}
            {docs.data && docs.data.items.length > 0 && (
              <>
                <div className="flex items-center gap-2">
                  {usable.length > 3 && (
                    <div className="relative flex-1">
                      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
                      <Input
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                        placeholder="Filter documents"
                        aria-label="Filter documents"
                        className="h-8 pl-8 text-[13px]"
                        disabled={busy}
                      />
                    </div>
                  )}
                  {usable.length > 0 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="ml-auto"
                      disabled={busy}
                      onClick={() =>
                        form.setValue("document_ids", selectedIds.length === usable.length ? [] : usable.map((d) => d.id), {
                          shouldValidate: true,
                        })
                      }
                    >
                      {selectedIds.length === usable.length ? "Clear" : "Select all"}
                    </Button>
                  )}
                </div>
                <Controller
                  control={form.control}
                  name="document_ids"
                  render={({ field }) => (
                    <fieldset disabled={busy}>
                      <legend className="sr-only">Select documents</legend>
                      <ul className="max-h-[26rem] divide-y divide-rule overflow-y-auto rounded-md border border-border">
                        {visibleUsable.map((d) => {
                          const checked = field.value.includes(d.id);
                          return (
                            <li key={d.id}>
                              <label
                                className={cn(
                                  "relative flex cursor-pointer items-start gap-3 px-3 py-2.5 transition-colors hover:bg-muted/50",
                                  checked && "bg-primary/[0.05]",
                                )}
                              >
                                <span aria-hidden className={cn("absolute inset-y-0 left-0 w-[2px]", checked ? "bg-primary" : "bg-transparent")} />
                                <Checkbox
                                  className="mt-0.5"
                                  checked={checked}
                                  onCheckedChange={(value) =>
                                    field.onChange(value ? [...field.value, d.id] : field.value.filter((x) => x !== d.id))
                                  }
                                  aria-label={documentTitle(d)}
                                />
                                <span className="min-w-0">
                                  <span className="block text-[13px] leading-snug font-medium">{documentTitle(d)}</span>
                                  <span className="mt-0.5 block font-mono text-[11px] text-muted-foreground">
                                    {[formatAuthors(d.authors, 1), d.publication_year, `${d.page_count ?? "?"} pp.`].filter(Boolean).join(" · ")}
                                  </span>
                                </span>
                              </label>
                            </li>
                          );
                        })}
                        {visibleUsable.length === 0 && usable.length > 0 && (
                          <li className="px-3 py-4 text-center text-xs text-muted-foreground">No document matches this filter.</li>
                        )}
                        {unusable.map((d) => (
                          <li key={d.id} className="flex items-center justify-between gap-3 px-3 py-2.5 opacity-75">
                            <span className="min-w-0 truncate pl-7 text-[13px]">{documentTitle(d)}</span>
                            <ProcessingBadge status={d.processing_status} />
                          </li>
                        ))}
                      </ul>
                    </fieldset>
                  )}
                />
                <p className="text-[11.5px] text-muted-foreground">
                  Only fully processed documents can be searched.{" "}
                  <Link href="/library" className="text-primary hover:underline">
                    Add documents
                  </Link>
                </p>
              </>
            )}
            {errors.document_ids && <p className="text-sm text-contradicted">{errors.document_ids.message}</p>}
          </div>
        </section>

        {/* 02 — Claim */}
        <section aria-labelledby="claim-heading" className="pane xl:col-start-2 xl:row-start-1">
          <PaneHeader index="02" label="Claim" title="Statement under examination" id="claim-heading" />
          <div className="space-y-5 p-5">
            <div className="space-y-1.5">
              <div className="flex items-baseline justify-between gap-3">
                <Label htmlFor="claim">Claim</Label>
                <span className="tabular font-mono text-[11px] text-muted-foreground" aria-hidden>
                  {(claimText ?? "").trim().length} / 2000
                </span>
              </div>
              <Textarea
                id="claim"
                rows={5}
                className="min-h-36 border-l-[3px] border-l-academic text-[16px]"
                placeholder="Dropout regularization reduces overfitting in neural networks."
                aria-invalid={!!errors.claim_text}
                aria-describedby={errors.claim_text ? "claim-error claim-hint" : "claim-hint"}
                disabled={busy}
                {...form.register("claim_text")}
              />
              <p id="claim-hint" className="text-xs text-muted-foreground">
                Be specific: include the population, intervention, outcome or conditions that matter.
              </p>
              {errors.claim_text && <p id="claim-error" className="text-sm text-contradicted">{errors.claim_text.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="title">Investigation title (optional)</Label>
              <Input id="title" placeholder="Defaults to the claim" disabled={busy} {...form.register("title")} />
              {errors.title && <p className="text-sm text-contradicted">{errors.title.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="context">Research context (optional)</Label>
              <Textarea
                id="context"
                rows={2}
                className="min-h-0"
                placeholder="e.g. Image classification with convolutional networks"
                disabled={busy}
                {...form.register("research_context")}
              />
              {errors.research_context && <p className="text-sm text-contradicted">{errors.research_context.message}</p>}
            </div>
          </div>
        </section>

        {/* 03 — Run */}
        <section aria-labelledby="run-heading" className="pane lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:sticky lg:top-16 xl:col-start-3">
          <PaneHeader index="03" label="Run" title="Investigation settings" id="run-heading" />
          <div className="space-y-5 p-5">
            <div className="space-y-1.5">
              <Label htmlFor="top_k">Passages to assess</Label>
              <Input
                id="top_k"
                type="number"
                min={3}
                max={20}
                className="font-mono"
                disabled={busy}
                {...form.register("top_k", { valueAsNumber: true })}
              />
              <p className="text-xs text-muted-foreground">
                The most relevant passages (3–20) are assessed individually. More passages give broader coverage and take longer.
              </p>
              {errors.top_k && <p className="text-sm text-contradicted">Choose a number between 3 and 20.</p>}
            </div>

            <div className="rounded-md border border-rule bg-muted/30 p-3">
              <p className="eyebrow mb-2">Pipeline</p>
              <ol className="space-y-1.5 text-[12.5px]">
                <PipelineLine n={1} label="Hybrid retrieval" detail={`keyword + semantic · top ${Number.isFinite(topK) ? topK : "—"}`} />
                <PipelineLine
                  n={2}
                  label="Passage assessment"
                  detail={assessmentConfigured === false ? "skipped: Gemini not configured" : "Gemini, one label per passage"}
                  muted={assessmentConfigured === false}
                />
                <PipelineLine n={3} label="Citation validation" detail="against stored passages" />
                <PipelineLine n={4} label="Verdict" detail="deterministic rules R1–R8" />
              </ol>
              <p className="mt-2 font-mono text-[11px] text-muted-foreground">
                Scope: {selectedIds.length} document{selectedIds.length === 1 ? "" : "s"} selected
              </p>
            </div>

            {busy ? (
              <ol className="space-y-2 text-sm" aria-live="polite">
                <Step done={phase === "verifying"} active={phase === "creating"} label="Saving investigation" />
                <Step done={false} active={phase === "verifying"} label="Retrieving, assessing and validating evidence" />
                <li className="pl-6 text-xs text-muted-foreground">This runs on the server in one step. Please keep this page open.</li>
              </ol>
            ) : (
              <Button type="submit" size="lg" className="w-full" disabled={docs.data?.items.length === 0}>
                <FileSearch /> Start verification
              </Button>
            )}
            {error && <ErrorState title="Verification could not run" message={error.message} requestId={error.requestId} />}
          </div>
        </section>
      </form>
    </>
  );
}

function PaneHeader({ index, label, title, id, aside }: { index: string; label: string; title: string; id: string; aside?: ReactNode }) {
  return (
    <div className="border-b border-rule px-5 py-3">
      <div className="flex items-baseline justify-between gap-3">
        <p className="eyebrow text-primary">
          {index} — {label}
        </p>
        {aside}
      </div>
      <h2 id={id} className="mt-0.5 text-[15px] font-semibold tracking-tight text-academic">
        {title}
      </h2>
    </div>
  );
}

function PipelineLine({ n, label, detail, muted = false }: { n: number; label: string; detail: string; muted?: boolean }) {
  return (
    <li className={cn("flex gap-2", muted && "text-muted-foreground")}>
      <span className="font-mono text-[11px] text-muted-foreground">{n}.</span>
      <span>
        <span className="font-medium">{label}</span>
        <span className="block text-[11.5px] text-muted-foreground">{detail}</span>
      </span>
    </li>
  );
}

function Step({ done, active, label }: { done: boolean; active: boolean; label: string }) {
  return (
    <li className={cn("flex items-center gap-2", !done && !active && "text-muted-foreground")}>
      {done ? (
        <CheckCircle2 className="size-4 text-supported" aria-hidden />
      ) : active ? (
        <Loader2 className="size-4 animate-spin text-primary" aria-hidden />
      ) : (
        <Circle className="size-4" aria-hidden />
      )}
      {label}
    </li>
  );
}
