import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap [&_svg]:size-3.5",
  {
    variants: {
      tone: {
        neutral: "border-border bg-neutral-soft text-muted-foreground",
        info: "border-primary/25 bg-primary/10 text-primary",
        success: "border-supported/25 bg-supported-soft text-supported",
        danger: "border-contradicted/25 bg-contradicted-soft text-contradicted",
        warning: "border-inconclusive/30 bg-inconclusive-soft text-inconclusive",
        ai: "border-ai/25 bg-mixed-soft text-ai",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

function Badge({ className, tone, ...props }: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span data-slot="badge" className={cn(badgeVariants({ tone }), className)} {...props} />;
}

export { Badge, badgeVariants };
