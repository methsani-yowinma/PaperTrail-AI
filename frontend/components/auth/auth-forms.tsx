"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { FlaskConical, Loader2, MailCheck } from "lucide-react";
import { toast } from "sonner";

import { Logo } from "@/components/layout/logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authEnabled } from "@/lib/config";
import { getBrowserSupabase } from "@/lib/supabase/client";

const email = z.string().trim().email("Enter a valid email address.");
const password = z.string().min(8, "Use at least 8 characters.");

export function AuthCard({ title, description, children, footer }: { title: string; description: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
      <Link href="/" className="mb-8">
        <Logo />
      </Link>
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-8">
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        <div className="mt-6">{authEnabled ? children : <LocalModeNotice />}</div>
      </div>
      {footer && authEnabled && <div className="mt-6 text-sm text-muted-foreground">{footer}</div>}
    </div>
  );
}

function LocalModeNotice() {
  return (
    <div className="space-y-4">
      <div className="flex gap-3 rounded-lg border border-inconclusive/30 bg-inconclusive-soft p-3 text-sm">
        <FlaskConical className="mt-0.5 size-4 shrink-0 text-inconclusive" aria-hidden />
        <p>
          Authentication is not configured, so the app is running in <strong>local development mode</strong> with a single
          local user. Set <code className="text-xs">NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
          <code className="text-xs">NEXT_PUBLIC_SUPABASE_ANON_KEY</code> to enable sign-in.
        </p>
      </div>
      <Button asChild className="w-full">
        <Link href="/dashboard">Continue in local mode</Link>
      </Button>
    </div>
  );
}

function Field({ id, label, error, children }: { id: string; label: string; error?: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error && (
        <p id={`${id}-error`} className="text-sm text-contradicted">
          {error}
        </p>
      )}
    </div>
  );
}

function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/dashboard";
}

const loginSchema = z.object({ email, password: z.string().min(1, "Enter your password.") });

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } });

  async function onSubmit(values: z.infer<typeof loginSchema>) {
    setServerError(null);
    const supabase = getBrowserSupabase();
    if (!supabase) return;
    const { error } = await supabase.auth.signInWithPassword(values);
    if (error) {
      setServerError(error.message === "Invalid login credentials" ? "Incorrect email or password." : error.message);
      return;
    }
    router.replace(safeNext(params.get("next")));
    router.refresh();
  }

  const { errors, isSubmitting } = form.formState;
  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <Field id="email" label="Email" error={errors.email?.message}>
        <Input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email} {...form.register("email")} />
      </Field>
      <Field id="password" label="Password" error={errors.password?.message}>
        <Input id="password" type="password" autoComplete="current-password" aria-invalid={!!errors.password} {...form.register("password")} />
      </Field>
      {serverError && <p role="alert" className="text-sm text-contradicted">{serverError}</p>}
      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting && <Loader2 className="animate-spin" />} Sign in
      </Button>
      <p className="text-center text-sm">
        <Link href="/reset-password" className="text-primary hover:underline">Forgot your password?</Link>
      </p>
    </form>
  );
}

const signupSchema = z
  .object({ displayName: z.string().trim().max(80).optional(), email, password, confirm: z.string() })
  .refine((v) => v.password === v.confirm, { message: "Passwords do not match.", path: ["confirm"] });

export function SignupForm() {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const [checkEmail, setCheckEmail] = useState(false);
  const form = useForm<z.infer<typeof signupSchema>>({
    resolver: zodResolver(signupSchema),
    defaultValues: { displayName: "", email: "", password: "", confirm: "" },
  });

  async function onSubmit(values: z.infer<typeof signupSchema>) {
    setServerError(null);
    const supabase = getBrowserSupabase();
    if (!supabase) return;
    const { data, error } = await supabase.auth.signUp({
      email: values.email,
      password: values.password,
      options: {
        data: { display_name: values.displayName || undefined },
        emailRedirectTo: `${window.location.origin}/auth/callback?next=/dashboard`,
      },
    });
    if (error) {
      setServerError(error.message);
      return;
    }
    if (data.session) {
      toast.success("Account created");
      router.replace("/dashboard");
      router.refresh();
    } else {
      setCheckEmail(true);
    }
  }

  if (checkEmail) {
    return (
      <div className="flex gap-3 rounded-lg border border-supported/30 bg-supported-soft p-4 text-sm">
        <MailCheck className="mt-0.5 size-5 shrink-0 text-supported" aria-hidden />
        <p>Check your inbox for a confirmation link to finish creating your account.</p>
      </div>
    );
  }

  const { errors, isSubmitting } = form.formState;
  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <Field id="displayName" label="Name (optional)" error={errors.displayName?.message}>
        <Input id="displayName" autoComplete="name" {...form.register("displayName")} />
      </Field>
      <Field id="email" label="Email" error={errors.email?.message}>
        <Input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email} {...form.register("email")} />
      </Field>
      <Field id="password" label="Password" error={errors.password?.message}>
        <Input id="password" type="password" autoComplete="new-password" aria-invalid={!!errors.password} {...form.register("password")} />
      </Field>
      <Field id="confirm" label="Confirm password" error={errors.confirm?.message}>
        <Input id="confirm" type="password" autoComplete="new-password" aria-invalid={!!errors.confirm} {...form.register("confirm")} />
      </Field>
      {serverError && <p role="alert" className="text-sm text-contradicted">{serverError}</p>}
      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting && <Loader2 className="animate-spin" />} Create account
      </Button>
    </form>
  );
}

const resetSchema = z.object({ email });

export function ResetRequestForm() {
  const [sent, setSent] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof resetSchema>>({ resolver: zodResolver(resetSchema), defaultValues: { email: "" } });

  async function onSubmit(values: z.infer<typeof resetSchema>) {
    setServerError(null);
    const supabase = getBrowserSupabase();
    if (!supabase) return;
    const { error } = await supabase.auth.resetPasswordForEmail(values.email, {
      redirectTo: `${window.location.origin}/auth/callback?next=/update-password`,
    });
    if (error) setServerError(error.message);
    else setSent(true);
  }

  if (sent) {
    return (
      <div className="flex gap-3 rounded-lg border border-supported/30 bg-supported-soft p-4 text-sm">
        <MailCheck className="mt-0.5 size-5 shrink-0 text-supported" aria-hidden />
        <p>If an account exists for that address, a password reset link is on its way.</p>
      </div>
    );
  }
  const { errors, isSubmitting } = form.formState;
  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <Field id="email" label="Email" error={errors.email?.message}>
        <Input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email} {...form.register("email")} />
      </Field>
      {serverError && <p role="alert" className="text-sm text-contradicted">{serverError}</p>}
      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting && <Loader2 className="animate-spin" />} Send reset link
      </Button>
    </form>
  );
}

const updateSchema = z
  .object({ password, confirm: z.string() })
  .refine((v) => v.password === v.confirm, { message: "Passwords do not match.", path: ["confirm"] });

export function UpdatePasswordForm() {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof updateSchema>>({ resolver: zodResolver(updateSchema), defaultValues: { password: "", confirm: "" } });

  async function onSubmit(values: z.infer<typeof updateSchema>) {
    setServerError(null);
    const supabase = getBrowserSupabase();
    if (!supabase) return;
    const { error } = await supabase.auth.updateUser({ password: values.password });
    if (error) {
      setServerError(error.message);
      return;
    }
    toast.success("Password updated");
    router.replace("/dashboard");
  }

  const { errors, isSubmitting } = form.formState;
  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <Field id="password" label="New password" error={errors.password?.message}>
        <Input id="password" type="password" autoComplete="new-password" aria-invalid={!!errors.password} {...form.register("password")} />
      </Field>
      <Field id="confirm" label="Confirm new password" error={errors.confirm?.message}>
        <Input id="confirm" type="password" autoComplete="new-password" aria-invalid={!!errors.confirm} {...form.register("confirm")} />
      </Field>
      {serverError && <p role="alert" className="text-sm text-contradicted">{serverError}</p>}
      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting && <Loader2 className="animate-spin" />} Update password
      </Button>
    </form>
  );
}
