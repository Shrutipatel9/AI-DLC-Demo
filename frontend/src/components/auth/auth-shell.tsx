import { LockKeyhole, ScanFace, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "@/components/brand/logo";

const HIGHLIGHTS = [
  { icon: ScanFace, text: "Landmark-based measurements of symmetry and proportions" },
  { icon: Sparkles, text: "A personal report with AI-generated visuals" },
  { icon: ShieldCheck, text: "Private by design: your photos are never shared" },
] as const;

// Public shell for sign-up, log-in, codes and password resets: a brand panel with the FaceIQ
// illustration on wide screens, and the form card beside it (on phones only the form shows).
export function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <aside
        aria-hidden="true"
        className="relative hidden w-[46%] max-w-[640px] flex-col justify-between overflow-hidden bg-surface-ink p-10 text-white lg:flex xl:p-12"
      >
        <div className="pointer-events-none absolute -left-32 -top-32 size-[420px] rounded-full bg-[#4f46e5] opacity-40 blur-[120px]" />
        <div className="pointer-events-none absolute -bottom-40 -right-24 size-[380px] rounded-full bg-[#0d9488] opacity-30 blur-[120px]" />
        <Logo tone="light" />
        <div className="relative">
          <p className="max-w-md font-display text-3xl font-bold leading-tight">
            Understand your face, <span className="text-[#a5b4fc]">feature by feature.</span>
          </p>
          <div className="mx-auto mt-8 aspect-[560/600] w-full max-w-[360px] rounded-[28px] bg-[url(/images/faceiq-hero.svg)] bg-cover shadow-2xl shadow-black/40" />
        </div>
        <ul className="relative space-y-3">
          {HIGHLIGHTS.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-center gap-3 text-[15px] text-[#cbd5e1]">
              <span className="inline-flex size-8 items-center justify-center rounded-lg bg-white/10">
                <Icon className="size-4 text-[#a5b4fc]" />
              </span>
              {text}
            </li>
          ))}
        </ul>
      </aside>

      <div className="flex min-h-screen flex-1 flex-col bg-dot-grid">
        <header>
          <nav aria-label="Main" className="flex items-center justify-between px-5 py-4 sm:px-8">
            <Link
              href="/"
              aria-label="FaceIQ home"
              className="rounded-lg lg:invisible"
              data-testid="header-wordmark-link"
            >
              <Logo />
            </Link>
          </nav>
        </header>
        <main
          id="main"
          className="mx-auto flex w-full max-w-[500px] flex-1 flex-col justify-center px-4 pb-12 pt-2"
        >
          <div className="rounded-card border border-card-border bg-white p-6 shadow-[0_24px_60px_-24px_rgb(15_23_42/0.22)] sm:p-9">
            <h1 className="mb-6 text-[28px] font-bold leading-tight text-heading">{title}</h1>
            {children}
          </div>
          <p className="mt-6 flex items-center justify-center gap-2 text-sm text-muted">
            <LockKeyhole className="size-4" aria-hidden="true" />
            Your photos and answers stay private
          </p>
        </main>
      </div>
    </div>
  );
}
