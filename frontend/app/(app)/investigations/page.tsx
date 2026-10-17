import type { Metadata } from "next";

import { InvestigationsList } from "@/components/verification/investigations-list";

export const metadata: Metadata = { title: "Investigations" };

export default function InvestigationsPage() {
  return <InvestigationsList />;
}
