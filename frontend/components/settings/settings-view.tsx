"use client";

import { useState } from "react";
import { CheckCircle2, Loader2, ShieldCheck, XCircle } from "lucide-react";

import { ErrorState, PageHeader } from "@/components/common/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { ApiError, api } from "@/lib/api";
import { authEnabled } from "@/lib/config";
import type { ModelCheck } from "@/types/api";

export function SettingsView() {
  const status = useApi(() => api.systemStatus(), []);
  const [check, setCheck] = useState<ModelCheck | null>(null);
  const [checking, setChecking] = useState(false);

  async function runCheck() {
    setChecking(true);
    try {
      setCheck(await api.checkModel());
    } catch (error) {
      setCheck({ ok: false, model: null, detail: null, error: error instanceof ApiError ? error.message : "Check failed." });
    } finally {
      setChecking(false);
    }
  }

  const s = status.data;
  const mismatch = s && ((s.auth_mode === "supabase") !== authEnabled);

  return (
    <>
      <PageHeader
        eyebrow="System"
        title="Settings"
        description="Current configuration of this PaperTrail AI installation. Server settings are managed through environment variables, not in the browser."
      />
      {status.error && <ErrorState message={status.error.message} onRetry={status.reload} />}
      {!s && !status.error && <Skeleton className="h-80 rounded-lg" />}
      {s && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader className="border-b border-rule">
              <CardTitle>Account and access</CardTitle>
              <CardDescription>How users are identified and how data is isolated.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2.5 pt-4 text-sm">
              <Row label="Authentication">
                {s.auth_mode === "supabase" ? <Badge tone="success">Supabase Auth</Badge> : <Badge tone="warning">Local development mode (no authentication)</Badge>}
              </Row>
              <Row label="Database">{s.database_backend === "postgres" ? "Supabase PostgreSQL + pgvector" : "Local SQLite (development)"}</Row>
              <Row label="File storage">{s.storage_backend === "supabase" ? "Private Supabase Storage bucket" : "Local disk (development)"}</Row>
              <Row label="Database reachable">{s.database_ok ? "Yes" : "No"}</Row>
              <Row label="Environment">{s.app_env}</Row>
              {mismatch && (
                <p className="rounded-lg border border-contradicted/30 bg-contradicted-soft p-3 text-contradicted">
                  The frontend and backend disagree about authentication. Configure Supabase on both, or on neither.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b border-rule">
              <CardTitle>Claim assessment</CardTitle>
              <CardDescription>Gemini judges individual passages; the verdict itself is computed by rules.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2.5 pt-4 text-sm">
              <Row label="Status">
                {s.assessment_configured ? <Badge tone="success">Configured</Badge> : <Badge tone="warning">Not configured</Badge>}
              </Row>
              <Row label="Configured model">{s.gemini_model ?? "—"}</Row>
              <Row label="Prompt version">{s.prompt_version}</Row>
              <Row label="Methodology version">{s.methodology_version}</Row>
              <div className="pt-2">
                <Button variant="outline" onClick={runCheck} disabled={checking || !s.assessment_configured}>
                  {checking ? <Loader2 className="animate-spin" /> : <ShieldCheck />} Check model access
                </Button>
                {!s.assessment_configured && (
                  <p className="mt-2 text-muted-foreground">Set GOOGLE_API_KEY and GEMINI_MODEL in backend/.env, then restart the backend.</p>
                )}
                {check && (
                  <p className={`mt-3 flex items-start gap-2 ${check.ok ? "text-supported" : "text-contradicted"}`} role="status">
                    {check.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden /> : <XCircle className="mt-0.5 size-4 shrink-0" aria-hidden />}
                    {check.ok ? `The model "${check.model}" is reachable with the configured key.` : check.error}
                  </p>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b border-rule">
              <CardTitle>Document processing</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5 pt-4 text-sm">
              <Row label="Embedding model">{s.embedding_model}</Row>
              <Row label="Vector dimension">{s.embedding_dimension}</Row>
              <Row label="Embedding provider">
                {s.embedding_provider === "hashing" ? <Badge tone="warning">Test-only hashing (not semantic)</Badge> : s.embedding_provider}
              </Row>
              <Row label="Upload limit">{s.max_upload_size_mb} MB · {s.max_pdf_pages} pages</Row>
              <Row label="OCR">Not available in this version (scanned PDFs are flagged)</Row>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-rule pb-2.5 last:border-b-0 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium break-all sm:text-right">{children}</span>
    </div>
  );
}
