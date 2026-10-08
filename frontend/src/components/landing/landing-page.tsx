"use client";

// The landing page (US2.1, US2.2; FR-001): a "Get started" button, a separate header "Sign in"
// link, and a "How it works" section showing questionnaire -> photos -> analysis -> report in
// order. Each step fades in as it scrolls into view; under reduced motion the steps simply
// appear (AC2.2.2). Copy is [Recommendation]: the client supplied no content for this page.
import Link from "next/link";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { useAuth } from "@/lib/auth";
import { useGoToNextStep } from "@/lib/journey";

export const HOW_IT_WORKS = [
  { title: "Answer a short questionnaire", text: "Tell us about your goals and what you like." },
  { title: "Add three photos", text: "A front photo and two 3/4 angles, checked as you go." },
  { title: "We analyse your face", text: "Measurements and an AI-written analysis, step by step." },
  { title: "Read your report", text: "Eleven features, your Home overview and a PDF to keep." },
] as const;

const BUTTON =
  "inline-flex min-h-11 items-center justify-center rounded-[var(--radius)] px-5 text-base font-semibold";

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
      className={`rounded-[var(--radius)] border border-card-border bg-card p-5 transition-all duration-700 ${
        shown ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
      }`}
    >
      <span
        aria-hidden="true"
        className="mb-2 inline-flex size-8 items-center justify-center rounded-full bg-accent-strong text-sm font-bold text-white"
      >
        {index + 1}
      </span>
      <h3 className="text-lg font-semibold text-heading">{title}</h3>
      <p className="mt-1 text-base text-foreground">{text}</p>
    </li>
  );
}

export function LandingPage() {
  const { status } = useAuth();
  const goToNextStep = useGoToNextStep();
  const signedIn = status === "signedIn";

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-card-border bg-white">
        <nav
          aria-label="Main"
          className="mx-auto flex max-w-[1200px] items-center justify-between px-4 py-3"
        >
          <Link
            href="/"
            className="text-lg font-bold text-heading"
            data-testid="header-wordmark-link"
          >
            <span aria-hidden="true">◆ </span>AI Facial Analysis
          </Link>
          {signedIn ? (
            <Link
              href="/home"
              className={`${BUTTON} border border-card-border bg-white text-heading hover:bg-[#eef2f5]`}
              data-testid="landing-account-link"
            >
              My account
            </Link>
          ) : (
            <Link
              href="/login"
              className={`${BUTTON} border border-card-border bg-white text-heading hover:bg-[#eef2f5]`}
              data-testid="landing-signin-link"
            >
              Sign in
            </Link>
          )}
        </nav>
      </header>
      <main id="main" className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-12">
        <section aria-labelledby="landing-title" className="mx-auto max-w-[720px] text-center">
          <h1 id="landing-title" className="text-4xl font-bold text-heading">
            Understand your face, feature by feature
          </h1>
          <p className="mt-4 text-lg text-foreground">
            Add three photos and get a personal facial analysis report with AI-generated visuals.
          </p>
          <Link
            href="/signup"
            onClick={(event) => {
              if (signedIn) {
                event.preventDefault();
                void goToNextStep();
              }
            }}
            className={`${BUTTON} mt-8 bg-accent-strong text-white hover:bg-[#1f6159]`}
            data-testid="landing-get-started"
          >
            Get started
          </Link>
        </section>

        <section aria-labelledby="how-title" className="mx-auto mt-16 max-w-[960px]">
          <h2 id="how-title" className="mb-6 text-center text-2xl font-bold text-heading">
            How it works
          </h2>
          <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="how-it-works">
            {HOW_IT_WORKS.map((step, index) => (
              <Step key={step.title} index={index} title={step.title} text={step.text} />
            ))}
          </ol>
        </section>
      </main>
    </div>
  );
}
