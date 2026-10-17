"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertTriangle, CheckCircle2, Circle, FileSearch, Loader2, Upload } from "lucide-react";
import { toast } from "sonner";

import { EmptyState, ErrorState, PageHeader } from "@/components/common/states";
import { ProcessingBadge } from "@/components/common/status-badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
  document_ids: z.array(z.string()).min(1, "Select at least one processed document."),
  top_k: z.number().int().min(3).max(20),
});
export type VerifyValues = z.infer<typeof verifySchema>;

type Phase = "idle" | "creating" | "verifying";

export function VerifyForm() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<ApiError | null>(null);
  const docs = useApi(() => api.listDocuments({ limit: 100 }), []);
  const system = useApi(() => api.systemStatus(), []);

  const form = useForm<VerifyValues>({
    resolver: zodResolver(verifySchema),
    defaultValues: { claim_text: "", title: "", research_context: "", document_ids: [], top_k: 8 },
  });

  const selectedIds = useWatch({ control: form.control, name: "document_ids" });
  const usable = docs.data?.items.filter((d) => d.processing_status === "completed") ?? [];
  const unusable = docs.data?.items.filter((d) => d.processing_status !== "completed") ?? [];

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

  return (
    <>
      <PageHeader
        title="Verify a claim"
        description="State a claim or research question, choose the documents to search, and PaperTrail AI will retrieve and assess the relevant evidence. Only your selected documents are searched, not the internet."
      />

      {system.data && !system.data.assessment_configured && (
        <div role="note" className="mb-6 flex gap-3 rounded-xl border border-inconclusive/30 bg-inconclusive-soft p-4 text-sm">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-inconclusive" aria-hidden />
          <p>
            <strong>Claim assessment is not configured.</strong> Retrieval will still run and you will see the relevant
            passages, but no verdict will be produced until <code className="text-xs">GOOGLE_API_KEY</code> and{" "}
            <code className="text-xs">GEMINI_MODEL</code> are set on the backend. See <Link href="/settings" className="text-primary underline">Settings</Link>.
          </p>
        </div>
      )}

      <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Claim or research question</CardTitle>
              <CardDescription>Be specific: include the population, intervention, outcome or conditions that matter.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="claim">Claim</Label>
                <Textarea
                  id="claim"
                  rows={3}
                  placeholder="Dropout regularization reduces overfitting in neural networks."
                  aria-invalid={!!errors.claim_text}
                  aria-describedby={errors.claim_text ? "claim-error" : undefined}
                  disabled={busy}
                  {...form.register("claim_text")}
                />
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
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-start justify-between gap-3">
              <div>
                <CardTitle>Documents to search</CardTitle>
                <CardDescription>Only fully processed documents can be searched.</CardDescription>
              </div>
              {usable.length > 0 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={busy}
                  onClick={() =>
                    form.setValue(
                      "document_ids",
                      selectedIds.length === usable.length ? [] : usable.map((d) => d.id),
                      { shouldValidate: true },
                    )
                  }
                >
                  {selectedIds.length === usable.length ? "Clear" : "Select all"}
                </Button>
              )}
            </CardHeader>
            <CardContent>
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
                <Controller
                  control={form.control}
                  name="document_ids"
                  render={({ field }) => (
                    <fieldset disabled={busy}>
                      <legend className="sr-only">Select documents</legend>
                      <ul className="max-h-80 divide-y divide-border overflow-y-auto rounded-lg border border-border">
                        {usable.map((d) => {
                          const checked = field.value.includes(d.id);
                          return (
                            <li key={d.id}>
                              <label className={cn("flex cursor-pointer items-start gap-3 px-3 py-2.5 hover:bg-muted/50", checked && "bg-primary/5")}>
                                <Checkbox
                                  className="mt-0.5"
                                  checked={checked}
                                  onCheckedChange={(value) =>
                                    field.onChange(value ? [...field.value, d.id] : field.value.filter((x) => x !== d.id))
                                  }
                                  aria-label={documentTitle(d)}
                                />
                                <span className="min-w-0">
                                  <span className="block truncate text-sm font-medium">{documentTitle(d)}</span>
                                  <span className="block text-xs text-muted-foreground">
                                    {[formatAuthors(d.authors, 2), d.publication_year, `${d.page_count ?? "?"} pages`].filter(Boolean).join(" · ")}
                                  </span>
                                </span>
                              </label>
                            </li>
                          );
                        })}
                        {unusable.map((d) => (
                          <li key={d.id} className="flex items-center justify-between gap-3 px-3 py-2.5 opacity-70">
                            <span className="min-w-0 truncate pl-7 text-sm">{documentTitle(d)}</span>
                            <ProcessingBadge status={d.processing_status} />
                          </li>
                        ))}
                      </ul>
                    </fieldset>
                  )}
                />
              )}
              {errors.document_ids && <p className="mt-2 text-sm text-contradicted">{errors.document_ids.message}</p>}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="lg:sticky lg:top-20">
            <CardHeader>
              <CardTitle>Investigation settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-1.5">
                <Label htmlFor="top_k">Passages to assess</Label>
                <Input
                  id="top_k"
                  type="number"
                  min={3}
                  max={20}
                  disabled={busy}
                  {...form.register("top_k", { valueAsNumber: true })}
                />
                <p className="text-xs text-muted-foreground">
                  The most relevant passages (3–20) are assessed individually. More passages give broader coverage and take longer.
                </p>
                {errors.top_k && <p className="text-sm text-contradicted">Choose a number between 3 and 20.</p>}
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
            </CardContent>
          </Card>
        </div>
      </form>
    </>
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
