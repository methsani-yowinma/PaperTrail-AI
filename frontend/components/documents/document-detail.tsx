"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ArrowLeft, ChevronLeft, ChevronRight, ExternalLink, FileText, Info } from "lucide-react";

import { ErrorState } from "@/components/common/states";
import { ProcessingBadge } from "@/components/common/status-badges";
import { DeleteDocumentButton, ReprocessButton } from "@/components/documents/document-actions";
import { MetadataEditor } from "@/components/documents/metadata-editor";
import { HighlightedPassage } from "@/components/evidence/highlighted-passage";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { cn, documentTitle, formatBytes, formatDateTime } from "@/lib/utils";

const SOURCE_LABELS: Record<string, string> = {
  pdf_metadata: "from PDF metadata",
  first_page_layout: "inferred from page layout, please verify",
  text_pattern: "matched in document text, please verify",
  user: "corrected by you",
};

export function DocumentDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const search = useSearchParams();
  const highlightChunk = search.get("chunk");
  const highlightStart = search.get("start");
  const highlightEnd = search.get("end");
  const initialPage = Number(search.get("page")) || 1;
  const [page, setPage] = useState(initialPage);

  const doc = useApi(() => api.getDocument(id), [id], {
    pollMs: 3000,
    pollWhile: (d) => d.processing_status === "pending" || d.processing_status === "processing",
  });
  const chunks = useApi(() => api.listChunks(id, page), [id, page, doc.data?.chunk_count], {
    enabled: doc.data?.processing_status === "completed",
  });
  const highlightRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (highlightRef.current) highlightRef.current.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [chunks.data]);

  const pageLabel = useMemo(() => {
    const labels = doc.data?.page_labels;
    return labels && labels[page - 1] ? labels[page - 1] : String(page);
  }, [doc.data?.page_labels, page]);

  if (doc.error) return <ErrorState message={doc.error.message} requestId={doc.error.requestId} onRetry={doc.reload} />;
  if (!doc.data) return <Skeleton className="h-96 rounded-xl" />;
  const d = doc.data;
  const pageCount = d.page_count ?? 0;

  return (
    <div className="space-y-6">
      <Link href="/library" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" aria-hidden /> Research Library
      </Link>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight">{documentTitle(d)}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{d.original_filename}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ProcessingBadge status={d.processing_status} />
          <Button asChild variant="outline" size="sm">
            <a href={`${api.documentFileUrl(d.id)}#page=${page}`} target="_blank" rel="noopener noreferrer">
              <ExternalLink /> Open PDF
            </a>
          </Button>
          <MetadataEditor doc={d} onSaved={doc.setData} />
          {d.processing_status !== "pending" && <ReprocessButton doc={d} onDone={doc.reload} />}
          <DeleteDocumentButton doc={d} onDeleted={() => router.replace("/library")} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Metadata</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="space-y-3 text-sm">
                <MetaRow label="Title" value={d.title} source={d.metadata_sources.title} />
                <MetaRow label="Authors" value={d.authors.length ? d.authors.join("; ") : null} source={d.metadata_sources.authors} />
                <MetaRow label="Year" value={d.publication_year?.toString() ?? null} source={d.metadata_sources.publication_year} />
                <MetaRow
                  label="DOI"
                  value={d.doi}
                  source={d.metadata_sources.doi}
                  href={d.doi ? `https://doi.org/${d.doi}` : undefined}
                />
                <MetaRow label="Source URL" value={d.source_url} href={d.source_url ?? undefined} />
                <MetaRow label="Pages" value={d.page_count?.toString() ?? null} />
                <MetaRow label="Passages" value={d.chunk_count ? d.chunk_count.toString() : null} />
                <MetaRow label="File size" value={formatBytes(d.file_size_bytes)} />
                <MetaRow label="Uploaded" value={formatDateTime(d.created_at)} />
                <MetaRow label="Embedding model" value={d.embedding_model} />
              </dl>
            </CardContent>
          </Card>
          {(d.processing_error || d.extraction_warnings.length > 0) && (
            <Card>
              <CardHeader>
                <CardTitle>Processing notes</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {d.processing_error && <p className="text-contradicted">{d.processing_error}</p>}
                {d.extraction_warnings.map((w) => (
                  <p key={w} className="flex gap-2">
                    <AlertTriangle className="mt-0.5 size-4 shrink-0 text-inconclusive" aria-hidden />
                    <span>{w}</span>
                  </p>
                ))}
              </CardContent>
            </Card>
          )}
        </div>

        <Card>
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
            <CardTitle>Extracted passages</CardTitle>
            {pageCount > 0 && d.processing_status === "completed" && (
              <div className="flex items-center gap-2">
                <Button variant="outline" size="icon" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                  <ChevronLeft />
                </Button>
                <span className="min-w-28 text-center text-sm">
                  Page {pageLabel}
                  <span className="text-muted-foreground"> ({page} of {pageCount})</span>
                </span>
                <Button variant="outline" size="icon" aria-label="Next page" disabled={page >= pageCount} onClick={() => setPage((p) => p + 1)}>
                  <ChevronRight />
                </Button>
              </div>
            )}
          </CardHeader>
          <CardContent>
            {d.processing_status !== "completed" ? (
              <p className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
                <Info className="size-4" aria-hidden />
                {d.processing_status === "needs_ocr"
                  ? "This document has no extractable text layer. OCR is not performed in this version."
                  : d.processing_status === "failed"
                    ? "Processing failed. Reprocess the document to try again."
                    : "Passages appear here when processing has completed."}
              </p>
            ) : chunks.loading && !chunks.data ? (
              <Skeleton className="h-48" />
            ) : chunks.error ? (
              <ErrorState message={chunks.error.message} onRetry={chunks.reload} />
            ) : chunks.data && chunks.data.length === 0 ? (
              <p className="py-8 text-sm text-muted-foreground">No indexed text on this page (it may be an image, a blank page or part of the reference list).</p>
            ) : (
              <ol className="space-y-4">
                {chunks.data?.map((chunk) => {
                  const highlighted = chunk.id === highlightChunk;
                  return (
                    <li key={chunk.id}>
                      <div
                        ref={highlighted ? highlightRef : undefined}
                        className={cn("rounded-lg border p-4", highlighted ? "border-primary bg-primary/5" : "border-border")}
                      >
                        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <FileText className="size-3.5" aria-hidden />
                          <span>Passage {chunk.chunk_index + 1}</span>
                          {chunk.section_title && <span>· {chunk.section_title}</span>}
                          {highlighted && <span className="font-medium text-primary">· Cited passage</span>}
                        </div>
                        <HighlightedPassage
                          text={chunk.content}
                          start={highlighted && highlightStart ? Number(highlightStart) : null}
                          end={highlighted && highlightEnd ? Number(highlightEnd) : null}
                        />
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function MetaRow({ label, value, source, href }: { label: string; value: string | null; source?: string; href?: string }) {
  return (
    <div>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 break-words">
        {value ? (
          href ? (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
              {value}
            </a>
          ) : (
            value
          )
        ) : (
          <span className="text-muted-foreground">Not available</span>
        )}
        {value && source && SOURCE_LABELS[source] && (
          <span className={cn("ml-1 text-xs", source === "user" || source === "pdf_metadata" ? "text-muted-foreground" : "text-inconclusive")}>
            ({SOURCE_LABELS[source]})
          </span>
        )}
      </dd>
    </div>
  );
}
