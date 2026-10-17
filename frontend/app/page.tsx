import Link from "next/link";
import {
  ArrowRight,
  BookOpenCheck,
  FileSearch,
  FileText,
  Fingerprint,
  Layers,
  Lock,
  Quote,
  ScrollText,
  ShieldCheck,
  Upload,
} from "lucide-react";

import { VerdictBadge } from "@/components/common/status-badges";
import { Logo } from "@/components/layout/logo";
import { Button } from "@/components/ui/button";
import { VERDICTS } from "@/lib/verdict";
import type { Verdict } from "@/types/api";

const STEPS = [
  {
    icon: Upload,
    title: "Build your library",
    body: "Upload research PDFs. Text is extracted page by page, so every passage keeps its exact page reference.",
  },
  {
    icon: FileSearch,
    title: "Ask a precise question",
    body: "State a claim and choose which documents to search. Hybrid keyword and semantic retrieval finds the relevant passages.",
  },
  {
    icon: BookOpenCheck,
    title: "Inspect the evidence",
    body: "Each passage is assessed individually, citations are checked against the stored text, and a rule-based verdict is explained.",
  },
];

const FEATURES = [
  { icon: Quote, title: "Traceable citations", body: "Every citation resolves to a stored passage, page number and document record. Unverifiable quotations are never shown." },
  { icon: Layers, title: "Hybrid retrieval", body: "Full-text and vector search are fused with reciprocal rank fusion, then filtered for relevance and duplicates." },
  { icon: Fingerprint, title: "Transparent reasoning", body: "Directness, evidence strength and evidence type are reported per passage, separately from retrieval relevance." },
  { icon: ScrollText, title: "Printable reports", body: "Turn any assessment into a structured evidence report with methodology and limitations, ready to print or export." },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <nav className="flex items-center gap-1 sm:gap-2" aria-label="Site">
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
              <a href="#how-it-works">How it works</a>
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
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pt-16 pb-20 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:pt-24">
          <div>
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
              <ShieldCheck className="size-3.5 text-supported" aria-hidden /> Research evidence &amp; claim verification
            </p>
            <h1 className="text-4xl font-semibold tracking-tight text-academic sm:text-5xl">Every answer should have evidence.</h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted-foreground">
              PaperTrail AI checks claims against the research papers you provide. It finds the relevant passages, assesses
              each one, and shows you exactly where every conclusion comes from, down to the page.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button asChild size="lg">
                <Link href="/verify">
                  Start an Investigation <ArrowRight />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <a href="#how-it-works">Explore How It Works</a>
              </Button>
            </div>
          </div>
          <ProductPreview />
        </section>

        {/* How it works */}
        <section id="how-it-works" className="border-y border-border bg-card py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <h2 className="text-2xl font-semibold tracking-tight text-academic sm:text-3xl">How it works</h2>
            <p className="mt-2 max-w-2xl text-muted-foreground">Three steps from a question to an inspectable evidence trail.</p>
            <ol className="mt-10 grid gap-6 md:grid-cols-3">
              {STEPS.map((step, index) => (
                <li key={step.title} className="rounded-xl border border-border bg-background p-6">
                  <div className="flex items-center gap-3">
                    <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <step.icon className="size-5" aria-hidden />
                    </span>
                    <span className="text-sm font-semibold text-muted-foreground">Step {index + 1}</span>
                  </div>
                  <h3 className="mt-4 text-lg font-semibold">{step.title}</h3>
                  <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">{step.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Features */}
        <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <h2 className="text-2xl font-semibold tracking-tight text-academic sm:text-3xl">Built for evidence, not eloquence</h2>
          <div className="mt-10 grid gap-5 sm:grid-cols-2">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-xl border border-border bg-card p-6">
                <f.icon className="size-5 text-primary" aria-hidden />
                <h3 className="mt-3 font-semibold">{f.title}</h3>
                <p className="mt-1.5 text-[15px] leading-relaxed text-muted-foreground">{f.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Evidence-grounded AI */}
        <section className="bg-academic py-20 text-white">
          <div className="mx-auto grid max-w-6xl gap-10 px-4 sm:px-6 lg:grid-cols-2">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Evidence-grounded AI</h2>
              <p className="mt-4 leading-relaxed text-white/80">
                A confident-sounding answer is not evidence. PaperTrail AI uses a language model only to judge individual
                passages that were retrieved from your documents. The model cannot add sources: it can refer only to
                passages the system gave it, and every citation is checked against the database before it is shown.
              </p>
            </div>
            <ul className="space-y-4 text-[15px]">
              {[
                "The overall verdict comes from documented, deterministic rules, not from the model's tone.",
                "Retrieval relevance, evidence strength and model confidence are shown separately and never merged into a fake probability.",
                "Text inside uploaded documents is treated as data. Embedded instructions are ignored.",
                "When the evidence is thin, the answer is Inconclusive.",
              ].map((line) => (
                <li key={line} className="flex gap-3 rounded-lg bg-white/5 p-4">
                  <ShieldCheck className="mt-0.5 size-5 shrink-0 text-white/70" aria-hidden />
                  <span className="text-white/90">{line}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* Outcomes */}
        <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <h2 className="text-2xl font-semibold tracking-tight text-academic sm:text-3xl">Four honest outcomes</h2>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Each outcome describes the evidence in the documents you selected, nothing more.
          </p>
          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {(Object.keys(VERDICTS) as Verdict[]).map((verdict) => (
              <div key={verdict} className={`rounded-xl border bg-card p-5 ${VERDICTS[verdict].border}`}>
                <VerdictBadge verdict={verdict} />
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{VERDICTS[verdict].description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Privacy */}
        <section className="border-t border-border bg-card py-16">
          <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 sm:px-6 md:flex-row md:items-start">
            <Lock className="size-8 shrink-0 text-academic" aria-hidden />
            <div>
              <h2 className="text-xl font-semibold text-academic">Privacy and transparency</h2>
              <p className="mt-2 max-w-3xl leading-relaxed text-muted-foreground">
                Uploaded PDFs are stored privately and are visible only to your account. Only the passages needed for an
                assessment are sent to the language model, never whole document collections, and API keys stay on the
                server. Every report records the model, prompt version and retrieval settings used, so results can be
                reviewed and reproduced.
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div className="flex items-center gap-3">
            <Logo compact />
            <span>PaperTrail AI: research evidence and claim verification.</span>
          </div>
          <nav className="flex gap-4" aria-label="Footer">
            <Link className="hover:text-foreground" href="/dashboard">App</Link>
            <a className="hover:text-foreground" href="#how-it-works">How it works</a>
            <Link className="hover:text-foreground" href="/login">Sign in</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}

function ProductPreview() {
  return (
    <figure aria-label="Illustrative preview of an evidence result" className="relative">
      <div className="rounded-2xl border border-border bg-card p-5 shadow-[0_12px_40px_-12px_rgba(24,52,119,0.25)]">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground">Claim</span>
          <span className="rounded bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">Illustration</span>
        </div>
        <p className="mt-1 font-medium">Dropout regularization reduces overfitting in neural networks.</p>
        <div className="mt-4 flex items-center gap-3">
          <VerdictBadge verdict="MIXED_EVIDENCE" size="lg" />
          <span className="text-xs text-muted-foreground">from 2 independent sources</span>
        </div>
        <div className="mt-4 space-y-3">
          <PreviewEvidence verdict="SUPPORTED" source="Example paper A · p. 6" text="…applying dropout reduced the gap between training and validation accuracy…" />
          <PreviewEvidence verdict="CONTRADICTED" source="Example paper B · p. 3" text="…dropout did not reduce overfitting for the largest models we evaluated…" />
        </div>
      </div>
      <figcaption className="mt-3 text-center text-xs text-muted-foreground">
        Illustrative example. Real results cite only your uploaded documents.
      </figcaption>
    </figure>
  );
}

function PreviewEvidence({ verdict, source, text }: { verdict: Verdict; source: string; text: string }) {
  const meta = VERDICTS[verdict];
  return (
    <div className={`rounded-lg border bg-background p-3 ${meta.border}`}>
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className={`inline-flex items-center gap-1 font-semibold ${meta.text}`}>
          <meta.icon className="size-3.5" aria-hidden /> {verdict === "SUPPORTED" ? "Supports" : "Contradicts"}
        </span>
        <span className="inline-flex items-center gap-1 text-muted-foreground">
          <FileText className="size-3.5" aria-hidden /> {source}
        </span>
      </div>
      <p className="mt-1.5 text-sm leading-relaxed text-foreground/90">{text}</p>
    </div>
  );
}
