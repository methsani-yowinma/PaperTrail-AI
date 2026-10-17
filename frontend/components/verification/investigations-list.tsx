"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, History, Plus, Search } from "lucide-react";

import { EmptyState, ErrorState, PageHeader } from "@/components/common/states";
import { InvestigationStatusBadge, VerdictBadge } from "@/components/common/status-badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatDateTime, pluralize } from "@/lib/utils";

const PAGE_SIZE = 20;

export function InvestigationsList() {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const t = window.setTimeout(() => {
      setDebounced(query.trim());
      setOffset(0);
    }, 250);
    return () => window.clearTimeout(t);
  }, [query]);

  const list = useApi(() => api.listInvestigations({ q: debounced, limit: PAGE_SIZE, offset }), [debounced, offset]);

  return (
    <>
      <PageHeader
        title="Investigations"
        description="Every claim you have checked, with its sources and latest verdict."
        actions={
          <Button asChild>
            <Link href="/verify">
              <Plus /> New Investigation
            </Link>
          </Button>
        }
      />
      <div className="relative mb-4 max-w-md">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search claims and titles" className="pl-9" aria-label="Search investigations" />
      </div>

      {list.error && <ErrorState message={list.error.message} requestId={list.error.requestId} onRetry={list.reload} />}
      {list.loading && !list.data && <Skeleton className="h-64 rounded-xl" />}
      {list.data && list.data.items.length === 0 && (
        <EmptyState
          icon={debounced ? Search : History}
          title={debounced ? "No matching investigations" : "No investigations yet"}
          description={debounced ? "Try a different search term." : "Verify a claim against your documents to start an investigation."}
          action={
            !debounced && (
              <Button asChild>
                <Link href="/verify">Verify a claim</Link>
              </Button>
            )
          }
        />
      )}
      {list.data && list.data.items.length > 0 && (
        <>
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
            {list.data.items.map((inv) => (
              <li key={inv.id}>
                <Link href={`/investigations/${inv.id}`} className="flex flex-col gap-2 px-4 py-3.5 hover:bg-muted/40 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{inv.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatDateTime(inv.created_at)} · {pluralize(inv.documents.length, "source")}
                    </p>
                  </div>
                  <div className="shrink-0">
                    {inv.overall_verdict ? <VerdictBadge verdict={inv.overall_verdict} /> : <InvestigationStatusBadge status={inv.status} />}
                  </div>
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

export function Pager({ total, offset, onChange, pageSize = PAGE_SIZE }: { total: number; offset: number; onChange: (o: number) => void; pageSize?: number }) {
  if (total <= pageSize) return null;
  return (
    <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
      <span>
        {offset + 1}–{Math.min(offset + pageSize, total)} of {total}
      </span>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - pageSize))}>
          <ChevronLeft /> Previous
        </Button>
        <Button variant="outline" size="sm" disabled={offset + pageSize >= total} onClick={() => onChange(offset + pageSize)}>
          Next <ChevronRight />
        </Button>
      </div>
    </div>
  );
}
