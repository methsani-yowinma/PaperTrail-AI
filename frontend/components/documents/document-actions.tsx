"use client";

import { useState } from "react";
import { Loader2, RotateCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

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
import { ApiError, api } from "@/lib/api";
import { documentTitle } from "@/lib/utils";
import type { DocumentItem } from "@/types/api";

export function ReprocessButton({ doc, onDone, size = "sm" }: { doc: DocumentItem; onDone: () => void; size?: "sm" | "default" }) {
  const [busy, setBusy] = useState(false);
  const disabled = busy || doc.processing_status === "processing" || doc.processing_status === "pending";
  return (
    <Button
      variant="outline"
      size={size}
      disabled={disabled}
      onClick={async () => {
        setBusy(true);
        try {
          await api.reprocessDocument(doc.id);
          toast.success("Reprocessing started");
          onDone();
        } catch (error) {
          toast.error(error instanceof ApiError ? error.message : "Could not start reprocessing.");
        } finally {
          setBusy(false);
        }
      }}
    >
      {busy ? <Loader2 className="animate-spin" /> : <RotateCw />} Reprocess
    </Button>
  );
}

export function DeleteDocumentButton({ doc, onDeleted, size = "sm" }: { doc: DocumentItem; onDeleted: () => void; size?: "sm" | "default" }) {
  const [busy, setBusy] = useState(false);
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" size={size} className="text-contradicted hover:bg-contradicted-soft" disabled={doc.processing_status === "processing"}>
          <Trash2 /> Delete
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this document?</AlertDialogTitle>
          <AlertDialogDescription>
            &ldquo;{documentTitle(doc)}&rdquo; and its extracted passages will be permanently deleted. Citations to it in
            existing reports will be shown as unavailable. This cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={busy}
            onClick={async (event) => {
              event.preventDefault();
              setBusy(true);
              try {
                await api.deleteDocument(doc.id);
                toast.success("Document deleted");
                onDeleted();
              } catch (error) {
                toast.error(error instanceof ApiError ? error.message : "Could not delete the document.");
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy && <Loader2 className="animate-spin" />} Delete document
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
