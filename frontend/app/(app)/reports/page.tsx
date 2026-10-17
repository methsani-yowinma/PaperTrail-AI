import type { Metadata } from "next";

import { ReportsList } from "@/components/reports/reports-list";

export const metadata: Metadata = { title: "Evidence Reports" };

export default function ReportsPage() {
  return <ReportsList />;
}
