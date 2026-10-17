import type { Metadata } from "next";
import Link from "next/link";

import { AuthCard, ResetRequestForm } from "@/components/auth/auth-forms";

export const metadata: Metadata = { title: "Reset password" };

export default function ResetPasswordPage() {
  return (
    <AuthCard
      title="Reset your password"
      description="We will email you a secure link to choose a new password."
      footer={<Link href="/login" className="text-primary hover:underline">Back to sign in</Link>}
    >
      <ResetRequestForm />
    </AuthCard>
  );
}
