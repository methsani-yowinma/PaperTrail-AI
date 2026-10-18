"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, FileText, FolderOpen, Search } from "lucide-react";

import { EmptyState, ErrorState, PageHeader } from "@/components/common/states";
import { ProcessingBadge } from "@/components/common/status-badges";
import { DeleteDocumentButton, ReprocessButton } from "@/components/documents/document-actions";
import { UploadDropzone } from "@/components/documents/upload-dropzone";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { documentTitle, formatAuthors, formatBytes, formatDate, pluralize } from "@/lib/utils";
import { PROCESSING } from "@/lib/verdict";
import type { ProcessingStatus } from "@/types/api";

const STATUS_FILTERS: Array<{ value: "" | ProcessingStatus; label: string }> = [
  { value: "", label: "All" },
  ...(Object.keys(PROCESSING) as ProcessingStatus[]).map((s) => ({ value: s, label: PROCESSING[s].label })),
];

export function LibraryView() {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState<"" | ProcessingStatus>("");
  const system = useApi(() => api.systemStatus(), []);

  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(query.trim()), 250);
    return () => window.clearTimeout(t);
  }, [query]);

  const docs = useApi(() => api.listDocuments({ q: debounced, status, limit: 100 }), [debounced, status], {
    pollMs: 3000,
    pollWhile: (page) => page.items.some((d) => d.processing_status === "pending" || d.processing_status === "processing"),
  });

  const isFiltered = Boolean(debounced || status);

  return (
    <>
      <PageHeader
        eyebrow="Corpus"
        title="Research Library"
        description="Upload research papers and technical documents. Each one is validated, split into page-anchored passages and indexed for search."
      />
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="order-2 space-y-4 lg:order-1">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by title, file name, author or DOI"
                className="pl-9"
                aria-label="Search documents"
              />
            </div>
            <div className="flex flex-wrap rounded-md border border-border bg-card p-0.5" role="group" aria-label="Filter by status">
              {STATUS_FILTERS.map((f) => (
                <button
                  key={f.value || "all"}
                  type="button"
                  onClick={() => setStatus(f.value)}
                  aria-pressed={status === f.value}
                  className={`rounded-[5px] px-2.5 py-1 text-xs font-medium transition-colors ${
                    status === f.value ? "bg-academic text-white" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {docs.error && <ErrorState message={docs.error.message} requestId={docs.error.requestId} onRetry={docs.reload} />}
          {docs.loading && !docs.data && (
            <div className="space-y-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-24 rounded-lg" />
              ))}
            </div>
          )}
          {docs.data && docs.data.items.length === 0 && (
            <EmptyState
              icon={isFiltered ? Search : FolderOpen}
              title={isFiltered ? "No matching documents" : "Your library is empty"}
              description={isFiltered ? "Try a different search term or status filter." : "Upload a PDF to start building your research library."}
            />
          )}
          {docs.data && docs.data.items.length > 0 && (
            <>
              <p className="eyebrow">{pluralize(docs.data.total, "document")}</p>
              <ul className="divide-y divide-rule overflow-hidden rounded-lg border border-border bg-card shadow-panel">
                {docs.data.items.map((doc) => (
                  <li key={doc.id} className="p-4 transition-colors hover:bg-muted/30">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="flex min-w-0 gap-3">
                        <span className="flex size-9 shrink-0 items-center justify-center rounded-md border border-border bg-muted/60 text-academic">
                          <FileText className="size-[18px]" aria-hidden />
                        </span>
                        <div className="min-w-0">
                          <Link href={`/library/${doc.id}`} className="rounded-sm leading-snug font-semibold text-foreground hover:text-primary hover:underline">
                            {documentTitle(doc)}
                          </Link>
                          <p className="mt-0.5 text-sm text-muted-foreground">
                            {[formatAuthors(doc.authors), doc.publication_year, doc.page_count ? pluralize(doc.page_count, "page") : null, formatBytes(doc.file_size_bytes)]
                              .filter(Boolean)
                              .join(" · ")}
                          </p>
                          <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                            {doc.original_filename} · uploaded {formatDate(doc.created_at)}
                            {doc.processing_status === "completed" ? ` · ${pluralize(doc.chunk_count, "passage")} indexed` : ""}
                          </p>
                          {doc.processing_error && <p className="mt-1.5 text-sm text-contradicted">{doc.processing_error}</p>}
                          {doc.extraction_warnings.length > 0 && (
                            <p className="mt-1.5 inline-flex items-center gap-1 text-xs text-inconclusive">
                              <AlertTriangle className="size-3.5" aria-hidden /> {pluralize(doc.extraction_warnings.length, "extraction warning")}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex shrink-0 flex-wrap items-center gap-2 sm:flex-col sm:items-end">
                        <ProcessingBadge status={doc.processing_status} />
                        <div className="flex gap-1">
                          {(doc.processing_status === "failed" || doc.processing_status === "needs_ocr") && (
                            <ReprocessButton doc={doc} onDone={docs.reload} />
                          )}
                          <DeleteDocumentButton doc={doc} onDeleted={docs.reload} />
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
        <aside className="order-1 lg:order-2">
          <div className="lg:sticky lg:top-20">
            <UploadDropzone maxMb={system.data?.max_upload_size_mb} onUploaded={docs.reload} />
          </div>
        </aside>
      </div>
    </>
  );
}
