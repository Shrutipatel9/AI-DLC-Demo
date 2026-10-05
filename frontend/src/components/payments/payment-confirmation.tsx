"use client";

// "Confirming your payment" (US6.5; FR7.4). Shown when Checkout sends the user back. Returning
// here proves nothing: the screen polls the server, whose status changes only when the verified
// webhook arrives. Until then "Start Analysis" is unavailable (AC6.5.1). When the confirmation
// arrives the screen updates without a reload and announces it to screen readers (AC6.5.2).
// After the configured wait it says the payment is still being confirmed, that the user won't
// be charged twice and can safely leave (AC6.5.3). The analysis never starts by itself.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef } from "react";

import { toast } from "@/components/feedback/toast";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { usePaymentConfirmation } from "@/lib/payments";

import {
  CONFIRMED_ANNOUNCEMENT,
  START_ANALYSIS_LOCKED,
  START_ANALYSIS_NOTE,
  STILL_CONFIRMING,
} from "./messages";
import { PAYMENT_STEP_LABEL } from "./payment-screen";

export function PaymentConfirmation({
  pollIntervalMs,
  onStartAnalysis,
}: {
  pollIntervalMs?: number;
  /** What "Start Analysis" does; U6 replaces the default with the analysis start. */
  onStartAnalysis?: () => void;
}) {
  const router = useRouter();
  const reasonId = useId();
  const { phase, waitedTooLong } = usePaymentConfirmation(pollIntervalMs);
  const previous = useRef(phase);

  useEffect(() => {
    // A real outcome of the payment action: confirm it with a toast when it arrives here.
    if (phase === "paid" && previous.current === "pending") {
      toast.success("Payment confirmed.");
    }
    previous.current = phase;
  }, [phase]);

  const paid = phase === "paid";
  const startAnalysis =
    onStartAnalysis ??
    // TODO(U6): replace with the "Start Analysis" call and the progress screen (US7.1). Until
    // that unit exists, the confirmed user goes back to the home page.
    (() => router.push("/home"));

  let title = "Checking your payment…";
  let message = "";
  if (phase === "pending") {
    title = "Confirming your payment";
    message = "We're waiting for the payment provider to confirm your payment.";
  } else if (paid) {
    title = "Payment confirmed";
    message = "Thank you. Your payment is confirmed.";
  }

  return (
    <div className="mx-auto max-w-[720px]">
      <p className="mb-3 text-sm font-medium text-muted" data-testid="payment-step-label">
        {PAYMENT_STEP_LABEL}
      </p>
      <Card className="p-4 sm:p-8">
        <p className="sr-only" role="status" aria-live="polite" data-testid="payment-announcement">
          {paid ? CONFIRMED_ANNOUNCEMENT : ""}
        </p>
        {phase === "none" ? (
          <section className="space-y-4" data-testid="payment-not-found">
            <h1 className="text-2xl font-bold text-heading">We couldn&apos;t find your payment</h1>
            <p className="text-base text-foreground">
              No payment has been started for your report yet.
            </p>
            <Link
              href="/payment"
              className="inline-flex min-h-11 items-center rounded-[var(--radius)] bg-accent-strong px-4 text-base font-semibold text-white hover:bg-[#1f6159]"
              data-testid="payment-back-link"
            >
              Go to payment
            </Link>
          </section>
        ) : (
          <section className="space-y-5" data-testid="payment-confirmation" data-state={phase}>
            <div>
              <h1
                className="text-2xl font-bold text-heading"
                data-testid="payment-confirmation-title"
              >
                {title}
              </h1>
              {message ? (
                <p className="mt-2 text-base text-muted" data-testid="payment-confirmation-message">
                  {message}
                </p>
              ) : null}
            </div>
            {waitedTooLong && !paid ? (
              <p
                className="rounded-[var(--radius)] border border-card-border bg-white p-3 text-base text-heading"
                data-testid="payment-still-confirming"
              >
                {STILL_CONFIRMING}
              </p>
            ) : null}
            <p className="text-base text-heading">{START_ANALYSIS_NOTE}</p>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                onClick={startAnalysis}
                disabled={!paid}
                aria-describedby={paid ? undefined : reasonId}
                data-testid="payment-start-analysis-button"
              >
                Start Analysis
              </Button>
              {paid ? null : (
                <p
                  id={reasonId}
                  className="text-sm text-heading"
                  data-testid="payment-start-reason"
                >
                  {START_ANALYSIS_LOCKED}
                </p>
              )}
            </div>
          </section>
        )}
      </Card>
    </div>
  );
}
