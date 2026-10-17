import type { Metadata } from "next";

import { LibraryView } from "@/components/documents/library-view";

export const metadata: Metadata = { title: "Research Library" };

export default function LibraryPage() {
  return <LibraryView />;
}
