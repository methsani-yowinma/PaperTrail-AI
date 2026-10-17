"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Pencil } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, api } from "@/lib/api";
import type { DocumentItem } from "@/types/api";

const schema = z.object({
  title: z.string().trim().max(500),
  authors: z.string().max(5000),
  publication_year: z
    .string()
    .trim()
    .refine((v) => v === "" || (/^\d{4}$/.test(v) && +v >= 1400 && +v <= 2200), "Enter a four-digit year."),
  doi: z
    .string()
    .trim()
    .refine((v) => v === "" || /^10\.\d{4,9}\/\S+$/.test(v), "A DOI looks like 10.1234/abcd (without https://doi.org/)."),
  source_url: z
    .string()
    .trim()
    .refine((v) => v === "" || /^https?:\/\/\S+$/.test(v), "Enter a full http(s) URL."),
});
type Values = z.infer<typeof schema>;

export function MetadataEditor({ doc, onSaved }: { doc: DocumentItem; onSaved: (doc: DocumentItem) => void }) {
  const [open, setOpen] = useState(false);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    values: {
      title: doc.title ?? "",
      authors: doc.authors.join("\n"),
      publication_year: doc.publication_year?.toString() ?? "",
      doi: doc.doi ?? "",
      source_url: doc.source_url ?? "",
    },
  });

  async function onSubmit(values: Values) {
    try {
      const updated = await api.updateDocument(doc.id, {
        title: values.title || null,
        authors: values.authors.split(/[\n;]/).map((a) => a.trim()).filter(Boolean),
        publication_year: values.publication_year ? Number(values.publication_year) : null,
        doi: values.doi || null,
        source_url: values.source_url || null,
      });
      toast.success("Metadata updated");
      onSaved(updated);
      setOpen(false);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not save metadata.");
    }
  }

  const { errors, isSubmitting } = form.formState;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Pencil /> Edit metadata
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Correct document metadata</DialogTitle>
          <DialogDescription>Your corrections are used in citations and reports, and are never overwritten by reprocessing.</DialogDescription>
        </DialogHeader>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <Label htmlFor="md-title">Title</Label>
            <Input id="md-title" {...form.register("title")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="md-authors">Authors (one per line)</Label>
            <Textarea id="md-authors" rows={3} className="min-h-0" {...form.register("authors")} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="md-year">Publication year</Label>
              <Input id="md-year" inputMode="numeric" aria-invalid={!!errors.publication_year} {...form.register("publication_year")} />
              {errors.publication_year && <p className="text-sm text-contradicted">{errors.publication_year.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="md-doi">DOI</Label>
              <Input id="md-doi" aria-invalid={!!errors.doi} {...form.register("doi")} />
              {errors.doi && <p className="text-sm text-contradicted">{errors.doi.message}</p>}
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="md-url">Source URL</Label>
            <Input id="md-url" type="url" aria-invalid={!!errors.source_url} {...form.register("source_url")} />
            {errors.source_url && <p className="text-sm text-contradicted">{errors.source_url.message}</p>}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="animate-spin" />} Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
