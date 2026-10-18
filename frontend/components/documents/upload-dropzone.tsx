"use client";

import { useRef, useState } from "react";
import { CheckCircle2, FileUp, Loader2, XCircle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError, uploadDocument } from "@/lib/api";
import { cn } from "@/lib/utils";

interface UploadItem {
  name: string;
  progress: number;
  state: "uploading" | "done" | "error";
  message?: string;
}

export function UploadDropzone({ maxMb, onUploaded }: { maxMb?: number; onUploaded: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [items, setItems] = useState<UploadItem[]>([]);
  const busy = items.some((i) => i.state === "uploading");

  function update(index: number, patch: Partial<UploadItem>) {
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  async function handleFiles(fileList: FileList | null) {
    if (!fileList?.length) return;
    const files = Array.from(fileList);
    const start = items.length;
    setItems((prev) => [...prev, ...files.map((f) => ({ name: f.name, progress: 0, state: "uploading" as const }))]);
    // Sequential uploads keep progress honest and avoid tripping the upload rate limit.
    for (const [offset, file] of files.entries()) {
      const index = start + offset;
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        update(index, { state: "error", message: "Only PDF files are supported." });
        continue;
      }
      if (maxMb && file.size > maxMb * 1024 * 1024) {
        update(index, { state: "error", message: `Larger than the ${maxMb} MB limit.` });
        continue;
      }
      try {
        await uploadDocument(file, (fraction) => update(index, { progress: fraction }));
        update(index, { state: "done", progress: 1, message: "Uploaded. Processing has started." });
        onUploaded();
      } catch (error) {
        const message = error instanceof ApiError ? error.message : "Upload failed.";
        update(index, { state: "error", message });
        toast.error(`${file.name}: ${message}`);
      }
    }
    if (input.current) input.current.value = "";
  }

  return (
    <section aria-labelledby="ingest-heading" className="pane space-y-0">
      <div className="border-b border-rule px-4 py-3">
        <p className="eyebrow text-primary">Ingest</p>
        <h2 id="ingest-heading" className="mt-0.5 text-[15px] font-semibold tracking-tight text-academic">
          Add research papers
        </h2>
      </div>
      <div className="space-y-3 p-4">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            void handleFiles(e.dataTransfer.files);
          }}
          className={cn(
            "bg-graph flex flex-col items-center justify-center gap-3 rounded-md border border-dashed px-5 py-7 text-center transition-colors",
            dragging ? "border-primary bg-primary/5" : "border-primary/30",
          )}
        >
          <span className="flex size-10 items-center justify-center rounded-md border border-border bg-card text-primary shadow-panel">
            <FileUp className="size-5" aria-hidden />
          </span>
          <div>
            <p className="font-medium">Drop PDF files here</p>
            <p className="text-sm text-muted-foreground">
              Text-based PDFs{maxMb ? ` up to ${maxMb} MB` : ""}. Scanned documents are flagged as needing OCR.
            </p>
          </div>
          <Button type="button" variant="outline" onClick={() => input.current?.click()} disabled={busy}>
            Choose files
          </Button>
          <input
            ref={input}
            type="file"
            accept="application/pdf,.pdf"
            multiple
            className="sr-only"
            aria-label="Choose PDF files to upload"
            onChange={(e) => void handleFiles(e.target.files)}
          />
        </div>
        {items.length > 0 && (
          <ul className="space-y-2" aria-live="polite">
            {items.map((item, i) => (
              <li key={`${item.name}-${i}`} className="rounded-md border border-border bg-card px-3 py-2">
                <div className="flex items-center gap-2 text-sm">
                  {item.state === "uploading" && <Loader2 className="size-4 animate-spin text-primary" aria-hidden />}
                  {item.state === "done" && <CheckCircle2 className="size-4 text-supported" aria-hidden />}
                  {item.state === "error" && <XCircle className="size-4 text-contradicted" aria-hidden />}
                  <span className="min-w-0 flex-1 truncate font-medium">{item.name}</span>
                  {item.state === "uploading" && <span className="tabular font-mono text-[11px] text-muted-foreground">{Math.round(item.progress * 100)}% uploaded</span>}
                </div>
                {item.state === "uploading" && (
                  <div className="mt-2 h-1 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={Math.round(item.progress * 100)} aria-valuemin={0} aria-valuemax={100} aria-label={`Uploading ${item.name}`}>
                    <div className="h-full bg-primary transition-[width]" style={{ width: `${item.progress * 100}%` }} />
                  </div>
                )}
                {item.message && (
                  <p className={cn("mt-1 text-xs", item.state === "error" ? "text-contradicted" : "text-muted-foreground")}>{item.message}</p>
                )}
              </li>
            ))}
          </ul>
        )}
        <ol className="space-y-1 border-t border-rule pt-3 text-[12px] text-muted-foreground" aria-label="What happens after upload">
          {["Validated by content, size and page count", "Text extracted page by page", "Split into page-anchored passages", "Indexed for keyword and semantic search"].map(
            (step, i) => (
              <li key={step} className="flex gap-2">
                <span className="font-mono text-[11px] text-primary">{String(i + 1).padStart(2, "0")}</span>
                {step}
              </li>
            ),
          )}
        </ol>
      </div>
    </section>
  );
}
