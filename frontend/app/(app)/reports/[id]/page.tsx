import type { Metadata } from "next";
import { Suspense } from "react";

import { ReportPage } from "@/components/reports/report-view";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Evidence Report" };

export default function EvidenceReportPage() {
  return (
    <Suspense fallback={<Skeleton className="h-[32rem] rounded-lg" />}>
      <ReportPage />
    </Suspense>
  );
}
