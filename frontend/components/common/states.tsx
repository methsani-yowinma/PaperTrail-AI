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
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow && <p className="mb-1 text-xs font-semibold tracking-wide text-primary uppercase">{eyebrow}</p>}
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
        {description && <p className="mt-1.5 max-w-2xl text-[15px] text-muted-foreground">{description}</p>}
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
    <div className={cn("flex flex-col items-center rounded-xl border border-dashed border-border bg-card px-6 py-12 text-center", className)}>
      <div className="mb-4 flex size-11 items-center justify-center rounded-full bg-muted text-academic">
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
    <div role="alert" className="rounded-xl border border-contradicted/30 bg-contradicted-soft px-5 py-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-contradicted" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-contradicted">{title}</p>
          <p className="mt-0.5 text-sm text-foreground">{message}</p>
          {requestId && <p className="mt-1 text-xs text-muted-foreground">Reference: {requestId}</p>}
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
