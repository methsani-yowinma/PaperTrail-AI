import type { Metadata } from "next";
import { Suspense } from "react";

import { DocumentDetail } from "@/components/documents/document-detail";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Document" };

export default function DocumentPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
      <DocumentDetail />
    </Suspense>
  );
}
