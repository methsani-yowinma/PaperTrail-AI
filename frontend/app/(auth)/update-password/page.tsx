import type { Metadata } from "next";

import { AuthCard, UpdatePasswordForm } from "@/components/auth/auth-forms";

export const metadata: Metadata = { title: "Choose a new password" };

export default function UpdatePasswordPage() {
  return (
    <AuthCard title="Choose a new password" description="Enter a new password for your account.">
      <UpdatePasswordForm />
    </AuthCard>
  );
}
