import { CheckCircle2, Clock, Loader2, ScanText, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { PROCESSING, RELATIONS, VERDICTS } from "@/lib/verdict";
import type { InvestigationStatus, PassageRelation, ProcessingStatus, Verdict } from "@/types/api";

const PROCESSING_ICONS = {
  pending: Clock,
  processing: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
  needs_ocr: ScanText,
} as const;

export function ProcessingBadge({ status }: { status: ProcessingStatus }) {
  const meta = PROCESSING[status];
  const Icon = PROCESSING_ICONS[status];
  return (
    <Badge tone={meta.tone}>
      <Icon className={cn(status === "processing" && "animate-spin")} aria-hidden />
      {meta.label}
    </Badge>
  );
}

export function VerdictBadge({ verdict, size = "sm" }: { verdict: Verdict; size?: "sm" | "lg" }) {
  const meta = VERDICTS[verdict];
  const Icon = meta.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[4px] border font-semibold whitespace-nowrap",
        meta.text,
        meta.soft,
        meta.border,
        size === "lg" ? "px-2.5 py-1 text-[15px] [&_svg]:size-[18px]" : "px-1.5 py-0.5 text-[11.5px] [&_svg]:size-3.5",
      )}
    >
      <Icon aria-hidden />
      {meta.label}
    </span>
  );
}

export function RelationBadge({ relation }: { relation: PassageRelation }) {
  const meta = RELATIONS[relation];
  const Icon = meta.icon;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-[4px] border px-1.5 py-0.5 text-[11.5px] font-semibold", meta.text, meta.soft, meta.border)}>
      <Icon className="size-3.5" aria-hidden />
      {meta.label}
    </span>
  );
}

export function InvestigationStatusBadge({ status }: { status: InvestigationStatus }) {
  switch (status) {
    case "running":
      return (
        <Badge tone="info">
          <Loader2 className="animate-spin" aria-hidden /> Running
        </Badge>
      );
    case "failed":
      return (
        <Badge tone="danger">
          <XCircle aria-hidden /> Failed
        </Badge>
      );
    case "completed":
      return (
        <Badge tone="success">
          <CheckCircle2 aria-hidden /> Completed
        </Badge>
      );
    default:
      return (
        <Badge>
          <Clock aria-hidden /> Not yet verified
        </Badge>
      );
  }
}
