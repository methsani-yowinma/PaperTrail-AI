"use client";

import Link from "next/link";
import { useState } from "react";
import { FileText } from "lucide-react";

import { EmptyState, ErrorState, PageHeader } from "@/components/common/states";
import { VerdictBadge } from "@/components/common/status-badges";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Pager } from "@/components/verification/investigations-list";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

export function ReportsList() {
  const [offset, setOffset] = useState(0);
  const list = useApi(() => api.listReports({ limit: 20, offset }), [offset]);

  return (
    <>
      <PageHeader
        title="Evidence Reports"
        description="One report per completed verification run. Reports are snapshots: re-running an investigation creates a new report."
      />
      {list.error && <ErrorState message={list.error.message} requestId={list.error.requestId} onRetry={list.reload} />}
      {list.loading && !list.data && <Skeleton className="h-64 rounded-xl" />}
      {list.data && list.data.items.length === 0 && (
        <EmptyState
          icon={FileText}
          title="No reports yet"
          description="A report is created each time an investigation is verified successfully."
          action={
            <Button asChild>
              <Link href="/verify">Verify a claim</Link>
            </Button>
          }
        />
      )}
      {list.data && list.data.items.length > 0 && (
        <>
          <ul className="grid gap-3 md:grid-cols-2">
            {list.data.items.map((r) => (
              <li key={r.id}>
                <Link href={`/reports/${r.id}`} className="block h-full rounded-xl border border-border bg-card p-4 transition-colors hover:border-primary/40">
                  <div className="flex items-start justify-between gap-3">
                    <p className="font-medium leading-snug">{r.investigation_title}</p>
                    {r.verdict && <VerdictBadge verdict={r.verdict} />}
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{r.claim_text}</p>
                  <p className="mt-2 text-xs text-muted-foreground">Assessed {formatDateTime(r.created_at)}</p>
                </Link>
              </li>
            ))}
          </ul>
          <Pager total={list.data.total} offset={offset} onChange={setOffset} />
        </>
      )}
    </>
  );
}
