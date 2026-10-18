import Link from "next/link";
import { ArrowRight, BookOpenCheck, FileStack, ListChecks, Lock, Quote, ScanSearch, Sparkles } from "lucide-react";

import { VerdictBadge } from "@/components/common/status-badges";
import { InterfacePreview } from "@/components/landing/interface-preview";
import { Logo } from "@/components/layout/logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { VERDICTS } from "@/lib/verdict";
import type { Verdict } from "@/types/api";

/** The real pipeline, stage by stage (see docs/AI_METHODOLOGY.md). */
const METHOD = [
  {
    stage: "Extract",
    body: "PDFs are validated by content, then read page by page. Reference lists are excluded from the index.",
    guarantee: "Every passage keeps one exact page.",
  },
  {
    stage: "Retrieve",
    body: "Full-text and vector search run over your selected documents only, fused with reciprocal rank fusion and filtered for relevance.",
    guarantee: "Nothing outside your selection is searched.",
  },
  {
    stage: "Assess",
    body: "A language model labels each retrieved passage independently: supports, contradicts, mixed or not relevant, with directness and strength.",
    guarantee: "The model can refer only to passages it was given.",
  },
  {
    stage: "Validate",
    body: "Each citation is re-checked against the database. A quotation is shown only if it is found in the stored passage text.",
    guarantee: "No citation is taken from model output.",
  },
  {
    stage: "Aggregate",
    body: "Documented, deterministic rules combine the validated assessments, counting each independent source once.",
    guarantee: "Thin evidence gives an Inconclusive verdict.",
  },
];

const TEXT_KINDS = [
  {
    icon: Quote,
    label: "Source text",
    title: "Verified quotations",
    body: "Sliced from the passage stored at upload time and anchored by character offsets. Shown with its document and page.",
    tone: "border-l-academic",
  },
  {
    icon: Sparkles,
    label: "AI assessment",
    title: "Model-generated rationale",
    body: "The model's reading of a passage, always labelled as AI-generated. It explains a label; it is never presented as a source.",
    tone: "border-dashed border-ai/40 border-l-ai",
  },
  {
    icon: ListChecks,
    label: "Verdict",
    title: "Rule-based finding",
    body: "Computed in code from validated assessments. The rule trace is shown, and model confidence is never used.",
    tone: "border-l-foreground/40",
  },
];

/** Shared section rhythm so every block lines up with the same container and spacing. */
const CONTAINER = "mx-auto w-full max-w-6xl px-4 sm:px-6 lg:px-8";
const SECTION_TITLE = "mt-2 text-[28px] leading-[1.15] font-semibold tracking-[-0.015em] text-academic sm:text-[32px]";
const SECTION_INTRO = "mt-3 max-w-2xl text-[16px] leading-relaxed text-muted-foreground";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-20 border-b border-border bg-card">
        <div className={cn(CONTAINER, "flex h-14 items-center justify-between gap-3")}>
          <Link href="/" className="shrink-0 rounded-sm" aria-label="PaperTrail AI home">
            <Logo />
          </Link>
          <nav className="flex items-center gap-1 sm:gap-2" aria-label="Site">
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
              <a href="#method">Method</a>
            </Button>
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
              <a href="#outcomes">Outcomes</a>
            </Button>
            <Button asChild variant="ghost" size="sm">
              <Link href="/login">Sign in</Link>
            </Button>
            <Button asChild size="sm">
              <Link href="/dashboard">Open app</Link>
            </Button>
          </nav>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="bg-graph border-b border-border">
          <div className={cn(CONTAINER, "grid items-center gap-12 pt-14 pb-16 sm:pt-20 sm:pb-20 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] lg:gap-14 lg:pt-24 lg:pb-28")}>
            <div className="min-w-0">
              <p className="eyebrow text-primary">Research evidence verification · within your corpus</p>
              <h1 className="mt-5 max-w-[34rem] text-[34px] leading-[1.1] font-semibold tracking-[-0.022em] text-balance text-academic sm:text-[42px] lg:text-[44px]">
                From research papers to <span className="whitespace-nowrap">evidence-backed</span> conclusions.
              </h1>
              <p className="mt-5 max-w-[32rem] text-[16.5px] leading-[1.65] text-muted-foreground">
                PaperTrail AI checks a claim against the PDFs you upload, assesses each relevant passage, and links every
                finding to its source page.
              </p>
              <HeroWorkflow />
              <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                <Button asChild size="lg">
                  <Link href="/verify">
                    Start an Investigation <ArrowRight />
                  </Link>
                </Button>
                <Button asChild size="lg" variant="outline">
                  <a href="#method">Read the method</a>
                </Button>
              </div>
            </div>
            <InterfacePreview />
          </div>
        </section>

        {/* Method */}
        <section id="method" className="scroll-mt-16 py-20 sm:py-24">
          <div className={CONTAINER}>
            <p className="eyebrow text-primary">Method</p>
            <h2 className={SECTION_TITLE}>From a claim to an inspectable evidence trail</h2>
            <p className={SECTION_INTRO}>Five stages, each with a guarantee you can check in the result.</p>
            <ol className="mt-10 overflow-hidden rounded-lg border border-border bg-card shadow-panel">
              {METHOD.map((step, index) => (
                <li
                  key={step.stage}
                  className="grid gap-3 border-b border-rule px-5 py-5 last:border-b-0 sm:px-6 md:grid-cols-[120px_minmax(0,1fr)_260px] md:gap-8"
                >
                  <div className="flex items-baseline gap-3 md:block">
                    <span className="font-mono text-[12px] text-primary">{String(index + 1).padStart(2, "0")}</span>
                    <h3 className="text-[16px] font-semibold tracking-tight text-academic md:mt-1">{step.stage}</h3>
                  </div>
                  <p className="text-[15px] leading-relaxed text-foreground/85">{step.body}</p>
                  <p className="border-t border-rule pt-3 font-mono text-[12px] leading-relaxed text-muted-foreground md:border-t-0 md:border-l md:pt-0 md:pl-6">
                    {step.guarantee}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Kinds of text */}
        <section className="border-y border-border bg-card py-20 sm:py-24">
          <div className={CONTAINER}>
            <p className="eyebrow text-primary">Evidence, not eloquence</p>
            <h2 className={SECTION_TITLE}>Three kinds of text, never blurred together</h2>
            <p className={SECTION_INTRO}>
              A fluent answer is not evidence. Every result keeps what the source says separate from what the model thinks and
              from how the verdict was reached.
            </p>
            <div className="mt-10 grid gap-4 sm:gap-5 md:grid-cols-3">
              {TEXT_KINDS.map((kind) => (
                <div key={kind.label} className={cn("rounded-lg border border-l-[3px] border-border bg-background p-5 sm:p-6", kind.tone)}>
                  <p className="eyebrow inline-flex items-center gap-1.5 text-academic">
                    <kind.icon className="size-3.5" aria-hidden /> {kind.label}
                  </p>
                  <h3 className="mt-3 text-[16px] font-semibold tracking-tight">{kind.title}</h3>
                  <p className="mt-1.5 text-[14.5px] leading-relaxed text-muted-foreground">{kind.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Outcomes */}
        <section id="outcomes" className="scroll-mt-16 py-20 sm:py-24">
          <div className={CONTAINER}>
            <p className="eyebrow text-primary">Outcomes</p>
            <h2 className={SECTION_TITLE}>Four honest outcomes</h2>
            <p className={SECTION_INTRO}>Each outcome describes the evidence in the documents you selected, nothing more.</p>
            <dl className="mt-10 overflow-hidden rounded-lg border border-border bg-card shadow-panel">
              {(Object.keys(VERDICTS) as Verdict[]).map((verdict) => (
                <div
                  key={verdict}
                  className="grid gap-2 border-b border-rule px-5 py-4 last:border-b-0 sm:grid-cols-[180px_minmax(0,1fr)] sm:items-center sm:gap-8 sm:px-6"
                >
                  <dt>
                    <VerdictBadge verdict={verdict} />
                  </dt>
                  <dd className="text-[14.5px] leading-relaxed text-muted-foreground">{VERDICTS[verdict].description}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        {/* Privacy */}
        <section className="border-t border-border bg-card py-14 sm:py-16">
          <div className={cn(CONTAINER, "flex flex-col gap-5 md:flex-row md:items-start md:gap-6")}>
            <span className="flex size-10 shrink-0 items-center justify-center rounded-md border border-border bg-background text-academic">
              <Lock className="size-5" aria-hidden />
            </span>
            <div>
              <h2 className="text-[17px] font-semibold tracking-tight text-academic">Privacy and reproducibility</h2>
              <p className="mt-2 max-w-3xl text-[14.5px] leading-relaxed text-muted-foreground">
                Uploaded PDFs are stored privately and are visible only to your account. Only the passages needed for an
                assessment are sent to the language model, never whole document collections, and API keys stay on the
                server. Every report records the model, prompt version and retrieval settings used.
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className={cn(CONTAINER, "flex flex-col gap-4 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between")}>
          <div className="flex items-center gap-3">
            <Logo compact />
            <span>PaperTrail AI: research evidence and claim verification.</span>
          </div>
          <nav className="flex gap-5" aria-label="Footer">
            <Link className="rounded-sm hover:text-foreground" href="/dashboard">App</Link>
            <a className="rounded-sm hover:text-foreground" href="#method">Method</a>
            <Link className="rounded-sm hover:text-foreground" href="/login">Sign in</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}

/** The product workflow in three steps, drawn as a connected sequence rather than cards. */
const WORKFLOW = [
  { icon: FileStack, title: "Research documents", body: "Upload PDFs and extract page-level evidence." },
  { icon: ScanSearch, title: "Claim analysis", body: "Retrieve relevant passages and assess their relationship to a claim." },
  { icon: BookOpenCheck, title: "Traceable findings", body: "Review verdicts, quotations, sources and page references." },
];

function HeroWorkflow() {
  return (
    <ol className="mt-8 max-w-[32rem]" aria-label="How PaperTrail AI works">
      {WORKFLOW.map((step, index) => {
        const last = index === WORKFLOW.length - 1;
        return (
          <li key={step.title} className={cn("relative flex gap-4", !last && "pb-5")}>
            {/* Thin connector from this step's icon to the next one. */}
            {!last && <span aria-hidden className="absolute top-10 bottom-1 left-[17.5px] w-px bg-primary/25" />}
            <span className="relative z-10 flex size-9 shrink-0 items-center justify-center rounded-md border border-primary/25 bg-card text-primary shadow-panel">
              <step.icon className="size-[18px]" strokeWidth={1.75} aria-hidden />
            </span>
            <div className="min-w-0 pt-0.5">
              <p className="flex items-baseline gap-2.5">
                <span className="font-mono text-[11px] text-primary">{String(index + 1).padStart(2, "0")}</span>
                <span className="text-[15px] font-semibold tracking-tight text-academic">{step.title}</span>
              </p>
              <p className="mt-0.5 text-[14px] leading-relaxed text-muted-foreground">{step.body}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
