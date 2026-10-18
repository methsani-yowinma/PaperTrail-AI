import type { LucideIcon } from "lucide-react";
import { AlertTriangle, RotateCw } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  eyebrow?: string;
}) {
  return (
    <div className="mb-7 flex flex-col gap-4 border-b border-border pb-5 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow && <p className="eyebrow mb-2 text-primary">{eyebrow}</p>}
        <h1 className="text-[26px] leading-tight font-semibold tracking-tight text-academic">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-[14.5px] leading-relaxed text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon: LucideIcon;
  title: string;
  description: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("bg-graph flex flex-col items-center rounded-lg border border-dashed border-primary/25 px-6 py-12 text-center", className)}>
      <div className="mb-4 flex size-10 items-center justify-center rounded-md border border-border bg-card text-academic shadow-panel">
        <Icon className="size-5" aria-hidden />
      </div>
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  requestId,
  onRetry,
}: {
  title?: string;
  message: string;
  requestId?: string | null;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="rounded-lg border border-contradicted/30 border-l-[3px] border-l-contradicted bg-contradicted-soft px-5 py-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-contradicted" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-contradicted">{title}</p>
          <p className="mt-0.5 text-sm text-foreground">{message}</p>
          {requestId && <p className="mt-1 font-mono text-[11px] text-muted-foreground">Reference: {requestId}</p>}
        </div>
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RotateCw /> Retry
          </Button>
        )}
      </div>
    </div>
  );
}
