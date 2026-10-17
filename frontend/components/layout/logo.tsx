import { cn } from "@/lib/utils";

/** PaperTrail AI mark: a document with a trail of linked citation points. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-8", className)} aria-hidden>
      <rect x="1" y="1" width="30" height="30" rx="8" fill="var(--pt-academic)" />
      <path d="M10 7.5h8.5l4.5 4.5v12.5H10z" fill="#fff" />
      <path d="M18.5 7.5V12H23" fill="none" stroke="var(--pt-academic)" strokeWidth="1.2" strokeLinejoin="round" opacity="0.35" />
      <path d="M13 15.5h7M13 18.5h5" stroke="var(--pt-academic)" strokeWidth="1.4" strokeLinecap="round" opacity="0.45" />
      <circle cx="13" cy="22" r="1.6" fill="var(--pt-interactive)" />
      <circle cx="18.5" cy="22" r="1.6" fill="var(--pt-interactive)" />
      <path d="M14.6 22h2.3" stroke="var(--pt-interactive)" strokeWidth="1.3" />
    </svg>
  );
}

export function Logo({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark />
      {!compact && (
        <span className="text-[17px] font-semibold tracking-tight text-academic">
          PaperTrail <span className="text-primary">AI</span>
        </span>
      )}
    </span>
  );
}
