"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { FlaskConical, LogOut, Menu, Plus, UserRound } from "lucide-react";
import { toast } from "sonner";

import { Logo } from "@/components/layout/logo";
import { NAV_GROUPS } from "@/components/layout/nav-items";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { authEnabled } from "@/lib/config";
import { getBrowserSupabase } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";

function NavList({ pathname, onNavigate }: { pathname: string | null; onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-5">
      {NAV_GROUPS.map((group) => (
        <div key={group.label}>
          <p className="mb-1.5 px-3 font-mono text-[10.5px] font-medium tracking-[0.14em] text-white/45 uppercase">{group.label}</p>
          <ul className="flex flex-col gap-0.5">
            {group.items.map(({ href, label, icon: Icon }) => {
              const active = pathname !== null && (pathname === href || pathname.startsWith(`${href}/`));
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative flex items-center gap-3 rounded-md px-3 py-[7px] text-[13.5px] font-medium transition-colors focus-visible:outline-white",
                      active ? "bg-white/[0.12] text-white" : "text-white/70 hover:bg-white/[0.06] hover:text-white",
                    )}
                  >
                    {/* Active marker: a thin rule, echoing the citation trail in the logo */}
                    <span
                      aria-hidden
                      className={cn("absolute top-1.5 bottom-1.5 left-0 w-[2px] rounded-full", active ? "bg-white" : "bg-transparent")}
                    />
                    <Icon className={cn("size-[17px]", active ? "text-white" : "text-white/55")} aria-hidden />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function ActiveNavList({ onNavigate }: { onNavigate?: () => void }) {
  return <NavList pathname={usePathname()} onNavigate={onNavigate} />;
}

/** The active-link highlight depends on the URL, so it streams in after the static shell. */
function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <Suspense fallback={<NavList pathname={null} onNavigate={onNavigate} />}>
      <ActiveNavList onNavigate={onNavigate} />
    </Suspense>
  );
}

function SidebarBody({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 px-3 py-4">
      <Link href="/dashboard" onClick={onNavigate} className="px-2 py-1 focus-visible:outline-white">
        <Logo tone="light" />
      </Link>
      <Link
        href="/verify"
        onClick={onNavigate}
        className="flex items-center gap-2 rounded-md border border-white/15 bg-white/[0.06] px-3 py-2 text-[13.5px] font-medium whitespace-nowrap text-white transition-colors hover:border-white/30 hover:bg-white/[0.1] focus-visible:outline-white"
      >
        <Plus className="size-4" aria-hidden /> New Investigation
      </Link>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <NavLinks onNavigate={onNavigate} />
      </div>
      <div className="rounded-md border border-white/10 px-3 py-2.5">
        <p className="font-mono text-[10.5px] tracking-[0.14em] text-white/45 uppercase">Scope</p>
        <p className="mt-1 text-[12px] leading-relaxed text-white/70">
          Verdicts reflect only the documents you select. They do not establish scientific truth.
        </p>
      </div>
    </div>
  );
}

function UserMenu() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const supabase = getBrowserSupabase();
    if (!supabase) return;
    void supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null));
    const { data } = supabase.auth.onAuthStateChange((_event, session) => setEmail(session?.user.email ?? null));
    return () => data.subscription.unsubscribe();
  }, []);

  if (!authEnabled) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-[4px] border border-inconclusive/30 bg-inconclusive-soft px-2 py-0.5 font-mono text-[11px] font-medium text-inconclusive">
        <FlaskConical className="size-3.5" aria-hidden /> Local mode
      </span>
    );
  }

  async function signOut() {
    const supabase = getBrowserSupabase();
    await supabase?.auth.signOut();
    toast.success("Signed out");
    router.replace("/login");
    router.refresh();
  }

  return (
    <div className="flex items-center gap-2">
      <span className="hidden items-center gap-2 text-sm text-muted-foreground sm:inline-flex">
        <UserRound className="size-4" aria-hidden />
        <span className="max-w-48 truncate">{email ?? "Signed in"}</span>
      </span>
      <Button variant="ghost" size="sm" onClick={signOut}>
        <LogOut /> Sign out
      </Button>
    </div>
  );
}

export function LocalModeBanner() {
  if (authEnabled) return null;
  return (
    <div role="note" className="border-b border-inconclusive/30 bg-inconclusive-soft px-4 py-2 text-center text-[13px] text-foreground">
      <strong className="font-semibold">Local development mode:</strong> authentication is disabled and all data
      belongs to a single local user. Configure Supabase before sharing this app.
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2">
        Skip to content
      </a>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 bg-academic text-white lg:block no-print">
        <SidebarBody />
      </aside>

      <Dialog open={mobileOpen} onOpenChange={setMobileOpen}>
        <DialogContent side="left" aria-describedby={undefined}>
          <DialogTitle className="sr-only">Navigation</DialogTitle>
          <SidebarBody onNavigate={() => setMobileOpen(false)} />
        </DialogContent>
      </Dialog>

      <div className="lg:pl-60">
        <div className="no-print">
          <LocalModeBanner />
        </div>
        <header className="sticky top-0 z-20 flex h-12 items-center gap-3 border-b border-border bg-card/90 px-4 backdrop-blur sm:px-6 no-print">
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <Menu />
          </Button>
          <Link href="/dashboard" className="lg:hidden">
            <Logo compact />
          </Link>
          <div className="ml-auto">
            <UserMenu />
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
