import {
  CircleCheck,
  CircleHelp,
  CircleSlash,
  CircleX,
  Scale,
  type LucideIcon,
} from "lucide-react";
import type { PassageRelation, ProcessingStatus, Verdict } from "@/types/api";

export interface StatusMeta {
  label: string;
  description: string;
  icon: LucideIcon;
  /** Tailwind classes built from design tokens */
  text: string;
  soft: string;
  border: string;
}

export const VERDICTS: Record<Verdict, StatusMeta> = {
  SUPPORTED: {
    label: "Supported",
    description: "Direct, decisive evidence in the selected documents supports the claim, and none contradicts it.",
    icon: CircleCheck,
    text: "text-supported",
    soft: "bg-supported-soft",
    border: "border-supported/30",
  },
  CONTRADICTED: {
    label: "Contradicted",
    description: "Direct, decisive evidence in the selected documents contradicts the claim, and none supports it.",
    icon: CircleX,
    text: "text-contradicted",
    soft: "bg-contradicted-soft",
    border: "border-contradicted/30",
  },
  MIXED_EVIDENCE: {
    label: "Mixed evidence",
    description: "The selected documents contain direct evidence pointing in different directions.",
    icon: Scale,
    text: "text-mixed",
    soft: "bg-mixed-soft",
    border: "border-mixed/30",
  },
  INCONCLUSIVE: {
    label: "Inconclusive",
    description: "There is not enough direct evidence in the selected documents to reach a conclusion.",
    icon: CircleHelp,
    text: "text-inconclusive",
    soft: "bg-inconclusive-soft",
    border: "border-inconclusive/30",
  },
};

export const RELATIONS: Record<PassageRelation, StatusMeta> = {
  SUPPORTS: { ...VERDICTS.SUPPORTED, label: "Supports", description: "This passage supports the claim." },
  CONTRADICTS: { ...VERDICTS.CONTRADICTED, label: "Contradicts", description: "This passage contradicts the claim." },
  MIXED: { ...VERDICTS.MIXED_EVIDENCE, label: "Mixed", description: "This passage reports mixed or conditional findings." },
  NOT_RELEVANT: {
    label: "Not relevant",
    description: "The passage does not provide evidence about this claim.",
    icon: CircleSlash,
    text: "text-muted-foreground",
    soft: "bg-neutral-soft",
    border: "border-border",
  },
  UNASSESSED: {
    label: "Not assessed",
    description: "The passage was retrieved but has not been assessed.",
    icon: CircleHelp,
    text: "text-muted-foreground",
    soft: "bg-neutral-soft",
    border: "border-border",
  },
};

export const PROCESSING: Record<ProcessingStatus, { label: string; tone: "neutral" | "info" | "success" | "danger" | "warning" }> = {
  pending: { label: "Pending", tone: "neutral" },
  processing: { label: "Processing", tone: "info" },
  completed: { label: "Completed", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  needs_ocr: { label: "Needs OCR", tone: "warning" },
};

export const EVIDENCE_TYPE_LABELS: Record<string, string> = {
  EXPERIMENTAL_RESULT: "Experimental result",
  AUTHOR_CONCLUSION: "Author conclusion",
  CITED_PRIOR_WORK: "Cites prior work",
  BACKGROUND_MENTION: "Background mention",
  OTHER: "Other",
};

export function titleCase(value: string | null | undefined): string {
  if (!value) return "—";
  return value.charAt(0) + value.slice(1).toLowerCase().replace(/_/g, " ");
}
