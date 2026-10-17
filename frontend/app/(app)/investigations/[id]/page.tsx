import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { InvestigationDetail } from "@/components/verification/investigation-detail";

export const metadata: Metadata = { title: "Investigation" };

export default function InvestigationPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
      <InvestigationDetail />
    </Suspense>
  );
}
