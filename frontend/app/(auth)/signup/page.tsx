import type { Metadata } from "next";
import Link from "next/link";

import { AuthCard, SignupForm } from "@/components/auth/auth-forms";

export const metadata: Metadata = { title: "Create account" };

export default function SignupPage() {
  return (
    <AuthCard
      title="Create your account"
      description="Your documents and investigations are private to your account."
      footer={
        <>
          Already have an account? <Link href="/login" className="text-primary hover:underline">Sign in</Link>
        </>
      }
    >
      <SignupForm />
    </AuthCard>
  );
}
