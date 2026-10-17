import type { Metadata } from "next";

import { VerifyForm } from "@/components/verification/verify-form";

export const metadata: Metadata = { title: "Verify a Claim" };

export default function VerifyPage() {
  return <VerifyForm />;
}
