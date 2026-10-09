"use client";

// "Confirming your payment" (US6.5; FR7.4). Shown when Checkout sends the user back. Returning
// here proves nothing: the screen polls the server, whose status changes only when the verified
// webhook arrives. Until then "Start Analysis" is unavailable (AC6.5.1). When the confirmation
// arrives the screen updates without a reload and announces it to screen readers (AC6.5.2).
// After the configured wait it says the payment is still being confirmed, that the user won't
// be charged twice and can safely leave (AC6.5.3). The analysis never starts by itself: only
// the "Start Analysis" click calls the server (US7.1, FR-015). A 409 about the photos shows its
// message and sends the user to the photo screen (AC7.1.2).
import { CircleCheck, LoaderCircle, ScanFace } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { analysisErrorMessage, needsPhotos } from "@/components/analysis/messages";
import { toast } from "@/components/feedback/toast";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { isApiError } from "@/lib/api/errors";
import { startAnalysis } from "@/lib/analysis";
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
  /** What "Start Analysis" does; the default starts the analysis and opens the progress screen. */
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

  const [starting, setStarting] = useState(false);

  const paid = phase === "paid";

  async function beginAnalysis() {
    setStarting(true);
    try {
      await startAnalysis();
      router.push("/analysis");
    } catch (error) {
      setStarting(false);
      if (isApiError(error) && error.code === "ANALYSIS_ALREADY_COMPLETE") {
        router.push("/analysis"); // already done: the progress screen shows the finished report
        return;
      }
      toast.error(isApiError(error) ? analysisErrorMessage(error) : "Something went wrong.");
      if (isApiError(error) && needsPhotos(error)) router.push("/photos");
    }
  }
  const onStart = onStartAnalysis ?? (() => void beginAnalysis());

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
      <p
        className="mb-3 inline-flex rounded-full border border-accent-soft-border bg-accent-soft px-3 py-1 text-sm font-semibold text-accent-deep"
        data-testid="payment-step-label"
      >
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
            <Link href="/payment" className={buttonVariants()} data-testid="payment-back-link">
              Go to payment
            </Link>
          </section>
        ) : (
          <section
            className="space-y-5 text-center"
            data-testid="payment-confirmation"
            data-state={phase}
          >
            <span
              aria-hidden="true"
              className={`mx-auto inline-flex size-16 items-center justify-center rounded-full ${
                paid ? "bg-success-soft text-success" : "bg-accent-soft text-accent-strong"
              }`}
            >
              {paid ? (
                <CircleCheck className="size-8" />
              ) : (
                <LoaderCircle className="size-8 animate-spin" />
              )}
            </span>
            <div>
              <h1
                className="text-2xl font-bold text-heading sm:text-[28px]"
                data-testid="payment-confirmation-title"
              >
                {title}
              </h1>
              {message ? (
                <p
                  className="mt-2 text-base text-subheading"
                  data-testid="payment-confirmation-message"
                >
                  {message}
                </p>
              ) : null}
            </div>
            {waitedTooLong && !paid ? (
              <p
                className="rounded-ui border border-[#fedf89] bg-[var(--warning-surface)] p-3 text-base text-heading"
                data-testid="payment-still-confirming"
              >
                {STILL_CONFIRMING}
              </p>
            ) : null}
            <p className="mx-auto max-w-md text-base text-subheading">{START_ANALYSIS_NOTE}</p>
            <div className="flex flex-col items-center gap-3">
              <Button
                onClick={onStart}
                disabled={!paid || starting}
                aria-describedby={paid ? undefined : reasonId}
                size="lg"
                data-testid="payment-start-analysis-button"
              >
                <ScanFace aria-hidden="true" />
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
