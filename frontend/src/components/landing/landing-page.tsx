"use client";

// The landing page (US2.1, US2.2; FR-001): a "Get started" button, a separate header "Sign in"
// link, and a "How it works" section showing questionnaire -> photos -> analysis -> report in
// order. Each step fades in as it scrolls into view; under reduced motion the steps simply
// appear (AC2.2.2). Copy is [Recommendation]: the client supplied no content for this page.
import {
  ArrowRight,
  Camera,
  ClipboardList,
  Clock,
  CreditCard,
  Download,
  FileText,
  HeartPulse,
  type LucideIcon,
  MessageCircle,
  Ruler,
  ScanFace,
  ShieldCheck,
  Sparkles,
  Wand2,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { type MouseEvent, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { Logo } from "@/components/brand/logo";
import { buttonVariants } from "@/components/ui/button";
import { IconTile } from "@/components/ui/page-header";
import { useAuth } from "@/lib/auth";
import { useGoToNextStep } from "@/lib/journey";
import { cn } from "@/lib/utils";

export const HOW_IT_WORKS = [
  { title: "Answer a short questionnaire", text: "Tell us about your goals and what you like." },
  { title: "Add three photos", text: "A front photo and two 3/4 angles, checked as you go." },
  { title: "We analyse your face", text: "Measurements and an AI-written analysis, step by step." },
  { title: "Read your report", text: "Eleven features, your Home overview and a PDF to keep." },
] as const;

const STEP_ICONS: readonly LucideIcon[] = [ClipboardList, Camera, ScanFace, FileText];

const FEATURES = [
  {
    icon: Ruler,
    tone: "indigo",
    title: "Symmetry & proportions",
    text: "Landmark-based measurements of balance, spacing and ratios across your face.",
  },
  {
    icon: ScanFace,
    tone: "teal",
    title: "Face shape",
    text: "Your face shape, explained with the measurements behind it.",
  },
  {
    icon: FileText,
    tone: "violet",
    title: "Feature-by-feature report",
    text: "Eleven features, each with an assessment and practical recommendations.",
  },
  {
    icon: Wand2,
    tone: "rose",
    title: "AI-generated visuals",
    text: "See suggested looks rendered on your own photo.",
  },
  {
    icon: MessageCircle,
    tone: "amber",
    title: "Beauty Assistant",
    text: "Ask follow-up questions about your report in a private chat.",
  },
  {
    icon: Download,
    tone: "indigo",
    title: "PDF to keep",
    text: "Download your full report and come back to it any time.",
  },
] as const;

const STATS = [
  { value: "11", label: "facial features analysed" },
  { value: "3", label: "photos is all it takes" },
  { value: "1", label: "personal, private report" },
] as const;

const PRIVACY = [
  {
    icon: ShieldCheck,
    title: "Your photos stay yours",
    text: "Stored privately and opened only for your own account.",
  },
  {
    icon: CreditCard,
    title: "Secure checkout",
    text: "Payments are handled by Stripe; we never see your card.",
  },
  {
    icon: HeartPulse,
    title: "Cosmetic, not medical",
    text: "Insights are about appearance only, never medical advice.",
  },
] as const;

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

/** True when the visitor's system asks for reduced motion (or cannot tell). */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return true;
  return window.matchMedia(REDUCED_MOTION).matches;
}

function subscribeToMotion(onChange: () => void): () => void {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => {};
  const query = window.matchMedia(REDUCED_MOTION);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function Step({ index, title, text }: { index: number; title: string; text: string }) {
  const ref = useRef<HTMLLIElement>(null);
  const [inView, setInView] = useState(false);
  // Reduced motion, or no IntersectionObserver: the step is simply there (AC2.2.2). The server
  // render assumes motion, so the markup matches until the browser's preference is read.
  const reduced = useSyncExternalStore(
    subscribeToMotion,
    () => prefersReducedMotion() || typeof IntersectionObserver === "undefined",
    () => false,
  );
  const shown = inView || reduced;
  const Icon = STEP_ICONS.at(index) ?? Sparkles;

  useEffect(() => {
    const element = ref.current;
    if (shown || !element) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold: 0.2 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [shown]);

  return (
    <li
      ref={ref}
      data-testid={`how-step-${index + 1}`}
      data-shown={shown ? "true" : "false"}
      style={{ transitionDelay: shown ? `${index * 90}ms` : undefined }}
      className={`relative rounded-card border border-card-border bg-white p-6 shadow-card transition-all duration-700 ${
        shown ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
      }`}
    >
      <div className="mb-4 flex items-center justify-between">
        <IconTile icon={Icon} />
        <span
          aria-hidden="true"
          className="font-display text-4xl font-extrabold text-accent-soft-border"
        >
          0{index + 1}
        </span>
      </div>
      <h3 className="text-lg font-bold text-heading">{title}</h3>
      <p className="mt-1.5 text-[15px] text-subheading">{text}</p>
    </li>
  );
}

export function LandingPage() {
  const { status } = useAuth();
  const goToNextStep = useGoToNextStep();
  const signedIn = status === "signedIn";

  // Signed in: "Get started" continues the journey instead of opening sign-up (AC2.1.3).
  function onStart(event: MouseEvent<HTMLAnchorElement>) {
    if (signedIn) {
      event.preventDefault();
      void goToNextStep();
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="sticky top-0 z-30 border-b border-card-border/70 bg-white/80 backdrop-blur-md">
        <nav
          aria-label="Main"
          className="mx-auto flex max-w-[1200px] items-center justify-between gap-4 px-4 py-3"
        >
          <Link
            href="/"
            aria-label="FaceIQ home"
            className="rounded-lg"
            data-testid="header-wordmark-link"
          >
            <Logo />
          </Link>
          <ul className="hidden items-center gap-1 md:flex">
            {[
              { href: "#features", label: "Features" },
              { href: "#how-it-works", label: "How it works" },
              { href: "#privacy", label: "Privacy" },
            ].map((item) => (
              <li key={item.href}>
                <a
                  href={item.href}
                  className="rounded-lg px-3 py-2 text-[15px] font-semibold text-subheading hover:bg-surface-muted hover:text-heading"
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
          {signedIn ? (
            <Link
              href="/home"
              className={buttonVariants({ variant: "secondary" })}
              data-testid="landing-account-link"
            >
              My account
            </Link>
          ) : (
            <Link
              href="/login"
              className={buttonVariants({ variant: "secondary" })}
              data-testid="landing-signin-link"
            >
              Sign in
            </Link>
          )}
        </nav>
      </header>

      <main id="main" className="flex-1">
        {/* Hero */}
        <section
          aria-labelledby="landing-title"
          className="relative overflow-hidden bg-brand-gradient-soft"
        >
          <div className="bg-dot-grid absolute inset-0 opacity-70" aria-hidden="true" />
          <div className="relative mx-auto grid max-w-[1200px] items-center gap-12 px-4 py-14 sm:py-20 lg:grid-cols-[1.05fr_1fr]">
            <div className="text-center lg:text-left">
              <p className="inline-flex items-center gap-2 rounded-full border border-accent-soft-border bg-white/80 px-3.5 py-1.5 text-sm font-semibold text-accent-deep shadow-sm">
                <Sparkles className="size-4" aria-hidden="true" />
                AI-powered facial analysis
              </p>
              <h1
                id="landing-title"
                className="mt-6 text-4xl font-extrabold leading-[1.08] text-heading sm:text-5xl lg:text-[58px]"
              >
                Understand your face,{" "}
                <span className="text-brand-gradient">feature by feature</span>
              </h1>
              <p className="mx-auto mt-5 max-w-xl text-lg text-subheading lg:mx-0">
                Add three photos and get a personal facial analysis report with AI-generated
                visuals.
              </p>
              <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center lg:justify-start">
                <Link
                  href="/signup"
                  onClick={onStart}
                  className={buttonVariants({ size: "lg" })}
                  data-testid="landing-get-started"
                >
                  Get started
                  <ArrowRight aria-hidden="true" />
                </Link>
                <a
                  href="#how-it-works"
                  className={buttonVariants({ variant: "secondary", size: "lg" })}
                >
                  See how it works
                </a>
              </div>
              <ul className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[15px] font-medium text-subheading lg:justify-start">
                <li className="flex items-center gap-2">
                  <Camera className="size-4 text-accent-strong" aria-hidden="true" />
                  Just three photos
                </li>
                <li className="flex items-center gap-2">
                  <Clock className="size-4 text-accent-strong" aria-hidden="true" />
                  Report in minutes
                </li>
                <li className="flex items-center gap-2">
                  <ShieldCheck className="size-4 text-accent-strong" aria-hidden="true" />
                  Private by design
                </li>
              </ul>
            </div>
            <div className="relative mx-auto w-full max-w-[520px]">
              <div
                aria-hidden="true"
                className="absolute -inset-6 rounded-[40px] bg-brand-gradient opacity-20 blur-3xl"
              />
              <Image
                src="/images/faceiq-hero.svg"
                alt="A face mapped with facial landmarks, showing a symmetry score and the face shape"
                width={560}
                height={600}
                priority
                unoptimized
                className="relative w-full rounded-[32px] border border-white shadow-raised"
              />
            </div>
          </div>
        </section>

        {/* Stats */}
        <section aria-label="FaceIQ at a glance" className="border-y border-card-border bg-white">
          <dl className="mx-auto grid max-w-[1200px] grid-cols-1 divide-y divide-card-border px-4 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            {STATS.map((stat) => (
              <div key={stat.label} className="flex flex-col items-center py-7">
                <dt className="order-2 text-[15px] text-subheading">{stat.label}</dt>
                <dd className="order-1 font-display text-4xl font-extrabold text-brand-gradient">
                  {stat.value}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        {/* Features */}
        <section
          id="features"
          aria-labelledby="features-title"
          className="mx-auto max-w-[1200px] scroll-mt-20 px-4 py-20"
        >
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-bold uppercase tracking-wider text-accent-strong">
              What you get
            </p>
            <h2 id="features-title" className="mt-2 text-3xl font-bold text-heading sm:text-4xl">
              A complete picture of your face
            </h2>
            <p className="mt-3 text-lg text-subheading">
              Clear measurements, honest explanations and practical ideas, all in one report.
            </p>
          </div>
          <ul className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feature) => (
              <li
                key={feature.title}
                className="group rounded-card border border-card-border bg-white p-6 shadow-card transition-all hover:-translate-y-0.5 hover:border-accent-soft-border hover:shadow-raised"
              >
                <IconTile icon={feature.icon} tone={feature.tone} />
                <h3 className="mt-4 text-lg font-bold text-heading">{feature.title}</h3>
                <p className="mt-1.5 text-[15px] text-subheading">{feature.text}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* How it works */}
        <section
          id="how-it-works"
          aria-labelledby="how-title"
          className="scroll-mt-20 bg-surface-muted/70 py-20"
        >
          <div className="mx-auto max-w-[1200px] px-4">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-bold uppercase tracking-wider text-accent-strong">
                Four simple steps
              </p>
              <h2 id="how-title" className="mt-2 text-3xl font-bold text-heading sm:text-4xl">
                How it works
              </h2>
            </div>
            <ol
              className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4"
              data-testid="how-it-works"
            >
              {HOW_IT_WORKS.map((step, index) => (
                <Step key={step.title} index={index} title={step.title} text={step.text} />
              ))}
            </ol>
          </div>
        </section>

        {/* Privacy */}
        <section
          id="privacy"
          aria-labelledby="privacy-title"
          className="mx-auto max-w-[1200px] scroll-mt-20 px-4 py-20"
        >
          <div className="relative overflow-hidden rounded-[28px] bg-surface-ink px-6 py-12 text-white sm:px-12">
            <div
              aria-hidden="true"
              className="absolute -right-20 -top-24 size-80 rounded-full bg-[#4f46e5] opacity-40 blur-[100px]"
            />
            <div className="relative grid gap-10 lg:grid-cols-[1fr_1.4fr] lg:items-center">
              <div>
                <ShieldCheck className="size-10 text-[#a5b4fc]" aria-hidden="true" />
                <h2 id="privacy-title" className="mt-4 text-3xl font-bold">
                  Built with privacy first
                </h2>
                <p className="mt-3 text-lg text-[#cbd5e1]">
                  Your face is personal. FaceIQ treats it that way.
                </p>
              </div>
              <ul className="grid gap-4 sm:grid-cols-3">
                {PRIVACY.map(({ icon: Icon, title, text }) => (
                  <li key={title} className="rounded-2xl border border-white/10 bg-white/5 p-5">
                    <Icon className="size-6 text-[#5eead4]" aria-hidden="true" />
                    <h3 className="mt-3 font-bold">{title}</h3>
                    <p className="mt-1 text-[15px] text-[#cbd5e1]">{text}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* Closing call to action */}
        <section aria-labelledby="cta-title" className="px-4 pb-20">
          <div className="mx-auto max-w-[1200px] rounded-[28px] bg-brand-gradient px-6 py-14 text-center text-white shadow-raised">
            <h2 id="cta-title" className="text-3xl font-bold sm:text-4xl">
              Ready to meet your FaceIQ?
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-lg text-white/85">
              It takes a few minutes to start and your report is yours to keep.
            </p>
            <Link
              href="/signup"
              onClick={onStart}
              className={cn(
                buttonVariants({ size: "lg" }),
                "mt-8 bg-white text-accent-deep shadow-lg hover:bg-white/90",
              )}
              data-testid="landing-cta-bottom"
            >
              Start my analysis
              <ArrowRight aria-hidden="true" />
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-card-border bg-white">
        <div className="mx-auto flex max-w-[1200px] flex-col items-center justify-between gap-4 px-4 py-8 sm:flex-row">
          <div className="flex flex-col items-center gap-2 sm:items-start">
            <Logo />
            <p className="text-sm text-muted">
              Cosmetic insights only. FaceIQ does not give medical advice.
            </p>
          </div>
          <nav aria-label="Footer">
            <ul className="flex items-center gap-5 text-sm font-semibold text-subheading">
              <li>
                <Link href="/login" className="hover:text-heading">
                  Sign in
                </Link>
              </li>
              <li>
                <Link href="/signup" className="hover:text-heading">
                  Create account
                </Link>
              </li>
              <li>© {new Date().getFullYear()} FaceIQ</li>
            </ul>
          </nav>
        </div>
      </footer>
    </div>
  );
}
