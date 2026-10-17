"use client";

import Link from "next/link";
import { ArrowRight, FileSearch, FileText, FolderOpen, History, Upload } from "lucide-react";

import { EmptyState, ErrorState, PageHeader } from "@/components/common/states";
import { InvestigationStatusBadge, ProcessingBadge, VerdictBadge } from "@/components/common/status-badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { documentTitle, formatDate } from "@/lib/utils";
import { PROCESSING } from "@/lib/verdict";
import type { ProcessingStatus } from "@/types/api";

export function DashboardView() {
  const { data, error, loading, reload } = useApi(() => api.dashboard(), [], {
    pollMs: 4000,
    pollWhile: (d) => d.recent_documents.some((doc) => doc.processing_status === "pending" || doc.processing_status === "processing"),
  });

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Your research library and recent investigations at a glance."
        actions={
          <Button asChild>
            <Link href="/verify">
              <FileSearch /> Verify a claim
            </Link>
          </Button>
        }
      />
      {error && <ErrorState message={error.message} requestId={error.requestId} onRetry={reload} />}
      {loading && !data && <DashboardSkeleton />}
      {data && (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <Stat label="Documents" value={data.documents_total} icon={FolderOpen} href="/library" />
            <Stat label="Investigations" value={data.investigations_total} icon={History} href="/investigations" />
            <Stat label="Evidence reports" value={data.reports_total} icon={FileText} href="/reports" />
          </div>

          {data.documents_total === 0 ? (
            <EmptyState
              icon={Upload}
              title="Start by adding research papers"
              description="Upload PDFs to your library. PaperTrail AI extracts their text page by page so claims can be checked against them."
              action={
                <Button asChild>
                  <Link href="/library">
                    <Upload /> Upload documents
                  </Link>
                </Button>
              }
            />
          ) : (
            <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
              <Card>
                <CardHeader className="flex-row items-center justify-between">
                  <CardTitle>Recent investigations</CardTitle>
                  <Link href="/investigations" className="text-sm text-primary hover:underline">View all</Link>
                </CardHeader>
                <CardContent>
                  {data.recent_investigations.length === 0 ? (
                    <p className="py-6 text-center text-sm text-muted-foreground">
                      No investigations yet. <Link href="/verify" className="text-primary hover:underline">Verify your first claim</Link>.
                    </p>
                  ) : (
                    <ul className="divide-y divide-border">
                      {data.recent_investigations.map((inv) => (
                        <li key={inv.id}>
                          <Link href={`/investigations/${inv.id}`} className="flex items-start justify-between gap-3 py-3 hover:bg-muted/40 -mx-2 px-2 rounded-md">
                            <div className="min-w-0">
                              <p className="truncate font-medium">{inv.title}</p>
                              <p className="text-xs text-muted-foreground">{formatDate(inv.created_at)} · {inv.documents.length} source(s)</p>
                            </div>
                            {inv.overall_verdict ? <VerdictBadge verdict={inv.overall_verdict} /> : <InvestigationStatusBadge status={inv.status} />}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>

              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Document processing</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <ul className="flex flex-wrap gap-2" aria-label="Documents by status">
                      {(Object.keys(PROCESSING) as ProcessingStatus[])
                        .filter((s) => data.documents_by_status[s])
                        .map((s) => (
                          <li key={s} className="inline-flex items-center gap-1.5">
                            <ProcessingBadge status={s} />
                            <span className="text-sm font-medium">{data.documents_by_status[s]}</span>
                          </li>
                        ))}
                    </ul>
                    <ul className="divide-y divide-border">
                      {data.recent_documents.map((doc) => (
                        <li key={doc.id} className="flex items-center justify-between gap-3 py-2">
                          <Link href={`/library/${doc.id}`} className="min-w-0 truncate text-sm hover:text-primary">
                            {documentTitle(doc)}
                          </Link>
                          <ProcessingBadge status={doc.processing_status} />
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex-row items-center justify-between">
                    <CardTitle>Recent reports</CardTitle>
                    <Link href="/reports" className="text-sm text-primary hover:underline">View all</Link>
                  </CardHeader>
                  <CardContent>
                    {data.recent_reports.length === 0 ? (
                      <p className="text-sm text-muted-foreground">Reports appear after an investigation is verified.</p>
                    ) : (
                      <ul className="divide-y divide-border">
                        {data.recent_reports.map((r) => (
                          <li key={r.id}>
                            <Link href={`/reports/${r.id}`} className="flex items-center justify-between gap-3 py-2.5 hover:text-primary">
                              <span className="min-w-0 truncate text-sm">{r.investigation_title}</span>
                              <ArrowRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

function Stat({ label, value, icon: Icon, href }: { label: string; value: number; icon: typeof FolderOpen; href: string }) {
  return (
    <Link href={href} className="group rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/40">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-muted-foreground">{label}</span>
        <Icon className="size-4 text-muted-foreground group-hover:text-primary" aria-hidden />
      </div>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-academic">{value}</p>
    </Link>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6" aria-label="Loading dashboard">
      <div className="grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-64 rounded-xl" />
    </div>
  );
}
