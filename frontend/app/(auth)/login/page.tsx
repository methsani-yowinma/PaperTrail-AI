import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { AuthCard, LoginForm } from "@/components/auth/auth-forms";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <AuthCard
      title="Sign in"
      description="Access your research library and investigations."
      footer={
        <>
          New to PaperTrail AI? <Link href="/signup" className="text-primary hover:underline">Create an account</Link>
        </>
      }
    >
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthCard>
  );
}
