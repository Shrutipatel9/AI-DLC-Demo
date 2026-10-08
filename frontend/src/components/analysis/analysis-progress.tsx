"use client";

// The analysis progress screen (US7.2, US7.11). It shows each step's state in words (done, in
// progress, waiting) and announces changes to screen readers through a polite live region
// without moving focus (AC7.2.1). It says the user can close the page and gives the configured
// expected wait (AC7.2.2); coming back later reads the same run (AC7.2.3). When the report is
// ready it offers "View my report" (Home Overview until the report screens exist, AC7.2.4).
// After a failed run it explains in plain language and offers the one free re-run; after a
// second failure it points to support (US7.11).
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { toast } from "@/components/feedback/toast";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useAnalysisProgress, type AnalysisRun } from "@/lib/analysis";

import {
  ANALYSIS_STEP_LABEL,
  FAILED_ANNOUNCEMENT,
  READY_ANNOUNCEMENT,
  STATE_TEXT,
  stepLabel,
  leaveNote,
  stepAnnouncement,
} from "./messages";

/** Where "View my report" goes until the report screens (U8) exist. */
export const REPORT_HREF = "/home";

function announcementFor(run: AnalysisRun | null): string {
  if (run === null) return "";
  if (run.status === "completed") return READY_ANNOUNCEMENT;
  if (run.status === "failed") return FAILED_ANNOUNCEMENT;
  const current = run.steps.find((step) => step.state === "current");
  return current ? stepAnnouncement(current.key) : "";
}

export function AnalysisProgress({ pollIntervalMs }: { pollIntervalMs?: number }) {
  const { phase, run, reload, rerun } = useAnalysisProgress(pollIntervalMs);
  const [rerunning, setRerunning] = useState(false);
  const previous = useRef(phase);

  useEffect(() => {
    // Real outcomes of the analysis: tell the user once, when it happens while they watch.
    if (previous.current === "running" && phase === "completed") {
      toast.success("Your report is ready.");
    } else if (previous.current === "running" && phase === "failed") {
      toast.error("Your analysis didn't finish.");
    }
    previous.current = phase;
  }, [phase]);

  async function runAgain() {
    setRerunning(true);
    const started = await rerun();
    setRerunning(false);
    if (started) toast.success("We've started your analysis again.");
    else toast.error("We couldn't start the re-run. Please try again.");
  }

  const live = (
    <p className="sr-only" role="status" aria-live="polite" data-testid="analysis-announcement">
      {announcementFor(run)}
    </p>
  );

  let body;
  if (phase === "loading") {
    body = (
      <p role="status" className="text-base text-muted" data-testid="analysis-loading">
        Loading your analysis…
      </p>
    );
  } else if (phase === "error") {
    body = (
      <div className="space-y-4" data-testid="analysis-error">
        <p role="alert" className="text-base text-heading">
          We couldn&apos;t load your analysis. Please try again.
        </p>
        <Button onClick={reload} data-testid="analysis-retry-button">
          Try again
        </Button>
      </div>
    );
  } else if (phase === "none" || run === null) {
    body = (
      <section className="space-y-4" data-testid="analysis-not-started">
        <h1 className="text-2xl font-bold text-heading">Your analysis hasn&apos;t started yet</h1>
        <p className="text-base text-muted">
          Your analysis starts only when you click Start Analysis after paying.
        </p>
        <Link
          href="/payment"
          className="inline-flex min-h-11 items-center rounded-[var(--radius)] bg-accent-strong px-4 text-base font-semibold text-white hover:bg-[#1f6159]"
          data-testid="analysis-payment-link"
        >
          Go to payment
        </Link>
      </section>
    );
  } else {
    const title =
      run.status === "completed"
        ? "Your report is ready"
        : run.status === "failed"
          ? "Something went wrong"
          : "Analysing your photos";
    body = (
      <section className="space-y-6" data-testid="analysis-progress" data-status={run.status}>
        <div>
          <h1 className="text-2xl font-bold text-heading" data-testid="analysis-title">
            {title}
          </h1>
          {run.status === "running" ? (
            <p className="mt-2 text-base text-muted" data-testid="analysis-leave-note">
              {leaveNote(run.expectedWaitMinutes)}
            </p>
          ) : null}
        </div>

        <ol className="space-y-3" aria-label="Analysis steps">
          {run.steps.map((step) => (
            <li
              key={step.key}
              className="flex items-baseline justify-between gap-4 rounded-[var(--radius)] border border-card-border bg-white p-3"
              data-testid={`analysis-step-${step.key}`}
              data-state={step.state}
              aria-current={step.state === "current" ? "step" : undefined}
            >
              <span className="text-base font-medium text-heading">{stepLabel(step.key)}</span>
              <span
                className="text-sm text-heading"
                data-testid={`analysis-step-${step.key}-state`}
              >
                {STATE_TEXT[step.state]}
              </span>
            </li>
          ))}
        </ol>

        {run.status === "completed" ? (
          <Link
            href={REPORT_HREF}
            className="inline-flex min-h-11 items-center rounded-[var(--radius)] bg-accent-strong px-4 text-base font-semibold text-white hover:bg-[#1f6159]"
            data-testid="analysis-view-report"
          >
            View my report
          </Link>
        ) : null}

        {run.status === "failed" ? (
          <div className="space-y-4" data-testid="analysis-failed">
            <p className="text-base text-heading" data-testid="analysis-failure-message">
              {run.failureMessage}
            </p>
            {run.rerunAvailable ? (
              <Button
                onClick={() => void runAgain()}
                disabled={rerunning}
                data-testid="analysis-rerun-button"
              >
                Try again for free
              </Button>
            ) : null}
            {run.contactSupport ? (
              <p
                className="text-base font-medium text-heading"
                data-testid="analysis-contact-support"
              >
                Please contact support. Your payment is safe and still covers this report.
              </p>
            ) : null}
          </div>
        ) : null}
      </section>
    );
  }

  return (
    <div className="mx-auto max-w-[720px]">
      <p className="mb-3 text-sm font-medium text-muted" data-testid="analysis-step-label">
        {ANALYSIS_STEP_LABEL}
      </p>
      <Card className="p-4 sm:p-8">
        {live}
        {body}
      </Card>
    </div>
  );
}
