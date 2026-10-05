"use client";

// The payment screen (US6.1, US6.2; FR7.1-FR7.3). It shows the configured price and currency
// from the server, what payment unlocks, and that the analysis starts only on "Start Analysis".
// It never shows any result or partial content (AC6.1.1). "Pay" asks the server for a hosted
// Checkout session (the same-person re-check runs there, BR-005) and sends the browser to it.
// `cancelled` is set by /payment/cancel: the user came back from Checkout without paying.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { toast } from "@/components/feedback/toast";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { isApiError, type ApiError } from "@/lib/api/errors";
import {
  formatPrice,
  getOffer,
  getPaymentStatus,
  goToCheckout,
  startCheckout,
  type Offer,
} from "@/lib/payments";

import { START_ANALYSIS_NOTE, needsPhotos, paymentErrorMessage } from "./messages";

export const PAYMENT_STEP_LABEL = "Step 4 of 5 · Payment";

type Screen = { kind: "loading" } | { kind: "error" } | { kind: "ready"; offer: Offer };

/** The offer, or "paid" when the user already paid (go to the confirmation), or "error". */
async function loadOffer(): Promise<Offer | "paid" | "error"> {
  try {
    const [offer, status] = await Promise.all([getOffer(), getPaymentStatus()]);
    return status.state === "paid" ? "paid" : offer;
  } catch (error) {
    if (isApiError(error)) toast.error(paymentErrorMessage(error));
    return "error";
  }
}

export function PaymentScreen({
  cancelled = false,
  navigate = goToCheckout,
}: {
  cancelled?: boolean;
  /** Full navigation to the hosted Checkout page (tests pass a mock). */
  navigate?: (url: string) => void;
}) {
  const router = useRouter();
  const [screen, setScreen] = useState<Screen>({ kind: "loading" });
  const [paying, setPaying] = useState(false);
  const [problem, setProblem] = useState<ApiError | null>(null);

  const apply = useCallback(
    (result: Awaited<ReturnType<typeof loadOffer>>) => {
      if (result === "paid") {
        router.replace("/payment/success");
      } else if (result === "error") {
        setScreen({ kind: "error" });
      } else {
        setScreen({ kind: "ready", offer: result });
      }
    },
    [router],
  );

  useEffect(() => {
    let active = true;
    void loadOffer().then((result) => {
      if (active) apply(result);
    });
    return () => {
      active = false;
    };
  }, [apply]);

  const load = useCallback(() => {
    setScreen({ kind: "loading" });
    void loadOffer().then(apply);
  }, [apply]);

  async function pay() {
    setPaying(true);
    setProblem(null);
    try {
      navigate(await startCheckout());
    } catch (error) {
      setPaying(false);
      if (isApiError(error) && error.code === "ALREADY_PAID") {
        router.replace("/payment/success");
        return;
      }
      if (isApiError(error)) setProblem(error);
      toast.error(isApiError(error) ? paymentErrorMessage(error) : "Something went wrong.");
    }
  }

  let body: ReactNode;
  if (screen.kind === "loading") {
    body = (
      <p role="status" className="text-base text-muted" data-testid="payment-loading">
        Loading your payment step…
      </p>
    );
  } else if (screen.kind === "error") {
    body = (
      <div className="space-y-4" data-testid="payment-error">
        <p role="alert" className="text-base text-heading">
          We couldn&apos;t load the payment step. Please try again.
        </p>
        <Button onClick={load} data-testid="payment-retry-button">
          Try again
        </Button>
      </div>
    );
  } else {
    const price = formatPrice(screen.offer.amount, screen.offer.currency);
    body = (
      <section className="space-y-6" data-testid="payment-screen">
        {cancelled ? (
          <p
            role="status"
            className="rounded-[var(--radius)] border border-card-border bg-white p-3 text-base text-heading"
            data-testid="payment-cancelled-notice"
          >
            Payment cancelled. You have not been charged.
          </p>
        ) : null}
        <div>
          <h1 className="text-2xl font-bold text-heading">Unlock your analysis</h1>
          <p className="mt-2 text-base text-muted">
            Your photos are ready. Pay once to unlock your personal report.
          </p>
        </div>
        <p className="text-3xl font-bold text-heading" data-testid="payment-price">
          {price}
        </p>
        <div>
          <h2 className="text-lg font-semibold text-heading">What you get</h2>
          <ul className="mt-2 list-disc space-y-1 pl-6 text-base" data-testid="payment-includes">
            {screen.offer.includes.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <p className="text-base text-heading" data-testid="payment-start-note">
          {START_ANALYSIS_NOTE}
        </p>
        {problem ? (
          <div
            role="alert"
            className="space-y-2 rounded-[var(--radius)] border-2 border-danger bg-white p-3"
            data-testid="payment-problem"
          >
            <p className="text-base text-heading">{paymentErrorMessage(problem)}</p>
            {needsPhotos(problem) ? (
              <Link
                href="/photos"
                className="text-base font-semibold text-accent-strong underline underline-offset-4"
                data-testid="payment-photos-link"
              >
                Review your photos
              </Link>
            ) : null}
          </div>
        ) : null}
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => void pay()} disabled={paying} data-testid="payment-pay-button">
            {paying ? "Opening secure checkout…" : `Pay ${price}`}
          </Button>
          <p className="text-sm text-muted">
            You&apos;ll pay on Stripe&apos;s secure checkout page.
          </p>
        </div>
      </section>
    );
  }

  return (
    <div className="mx-auto max-w-[720px]">
      <p className="mb-3 text-sm font-medium text-muted" data-testid="payment-step-label">
        {PAYMENT_STEP_LABEL}
      </p>
      <Card className="p-4 sm:p-8">{body}</Card>
    </div>
  );
}
