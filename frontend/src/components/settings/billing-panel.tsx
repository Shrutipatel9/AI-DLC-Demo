"use client";

// Settings -> Billing (US11.6): the payment history, and the payment options. Stripe is
// available; PayPal is visible but disabled with a "not available" label that screen readers
// announce, and activating it does nothing (AC11.6.2; PayPal is never a working integration).
import { Button } from "@/components/ui/button";
import { formatPrice } from "@/lib/payments";
import { useBilling } from "@/lib/settings";

import { formatDate, statusText } from "./format";

function PaymentOptions() {
  return (
    <section aria-labelledby="payment-options-heading" className="mt-8">
      <h3 id="payment-options-heading" className="mb-3 text-lg font-semibold text-heading">
        Payment options
      </h3>
      <ul className="space-y-2">
        <li
          className="flex items-center justify-between rounded-[var(--radius)] border border-card-border px-4 py-3"
          data-testid="payment-option-stripe"
        >
          <span className="text-base text-heading">Stripe</span>
          <span className="text-sm font-medium text-heading">Available</span>
        </li>
        <li>
          <button
            type="button"
            aria-disabled="true"
            aria-describedby="paypal-unavailable"
            onClick={(event) => event.preventDefault()}
            className="flex w-full cursor-not-allowed items-center justify-between rounded-[var(--radius)] border border-card-border bg-[#f3f4f6] px-4 py-3 text-left"
            data-testid="payment-option-paypal"
          >
            <span className="text-base text-heading">PayPal</span>
            <span id="paypal-unavailable" className="text-sm font-medium text-heading">
              Not available
            </span>
          </button>
        </li>
      </ul>
    </section>
  );
}

export function BillingPanel() {
  const billing = useBilling();

  let history;
  if (billing.phase === "loading") {
    history = (
      <p role="status" className="text-base text-muted" data-testid="billing-loading">
        Loading your payments…
      </p>
    );
  } else if (billing.phase === "error" || !billing.data) {
    history = (
      <div className="space-y-4" data-testid="billing-error">
        <p role="alert" className="text-base text-heading">
          We couldn&apos;t load your payments. Please try again.
        </p>
        <Button onClick={billing.reload} data-testid="billing-retry-button">
          Try again
        </Button>
      </div>
    );
  } else if (billing.data.payments.length === 0) {
    history = (
      <p className="text-base text-muted" data-testid="billing-empty">
        You haven&apos;t made a payment yet.
      </p>
    );
  } else {
    history = (
      <div className="overflow-x-auto">
        <table className="w-full text-left text-base" data-testid="billing-table">
          <caption className="sr-only">Your payments, newest first</caption>
          <thead>
            <tr className="border-b border-card-border text-sm text-muted">
              <th scope="col" className="py-2 pr-4 font-medium">
                Date
              </th>
              <th scope="col" className="py-2 pr-4 font-medium">
                Amount
              </th>
              <th scope="col" className="py-2 pr-4 font-medium">
                Currency
              </th>
              <th scope="col" className="py-2 font-medium">
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {billing.data.payments.map((payment, index) => (
              <tr
                key={`${payment.date}-${index}`}
                className="border-b border-card-border last:border-0"
                data-testid="billing-row"
              >
                <td className="py-2 pr-4">{formatDate(payment.date)}</td>
                <td className="py-2 pr-4">{formatPrice(payment.amount, payment.currency)}</td>
                <td className="py-2 pr-4">{payment.currency}</td>
                <td className="py-2">{statusText(payment.status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div>
      {history}
      <PaymentOptions />
    </div>
  );
}
