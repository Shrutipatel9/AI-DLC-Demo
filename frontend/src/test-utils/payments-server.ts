// A small, stateful stand-in for the /payments API (contract C1), used with `mockFetch` in
// component tests. The status answers come from `states` in order (the last one repeats), so a
// test can script "pending, pending, paid" the way the webhook would. Test-only module.
import type { components } from "@/lib/api/types.gen";

import { errorResponse, jsonResponse, type RecordedRequest } from "./fetch-mock";

type Offer = components["schemas"]["OfferOut"];
type State = components["schemas"]["PaymentStatusOut"]["state"];

export const TEST_OFFER: Offer = {
  amount: 2900,
  currency: "USD",
  includes: [
    "Your full facial analysis report covering 11 features, with a PDF to download",
    "AI-generated visuals of suggested looks",
    "The AI Beauty Assistant, answering questions about your report",
  ],
};

export interface PaymentsServerState {
  offer: Offer;
  states: State[];
  confirmWaitSeconds: number;
  checkoutUrl: string;
  /** When set, POST /payments/checkout answers this error instead. */
  checkoutError: { status: number; code: string; details?: unknown[] } | null;
  /** When true, every GET fails with 500 (load errors). */
  failReads: boolean;
  checkouts: number;
}

export function newPaymentsState(
  overrides: Partial<PaymentsServerState> = {},
): PaymentsServerState {
  return {
    offer: TEST_OFFER,
    states: ["none"],
    confirmWaitSeconds: 30,
    checkoutUrl: "https://checkout.example.test/c/pay/cs_test_1",
    checkoutError: null,
    failReads: false,
    checkouts: 0,
    ...overrides,
  };
}

/** A `mockFetch` handler serving /payments/offer, /payments/checkout and /payments/status. */
export function paymentsServer(state: PaymentsServerState) {
  return (request: RecordedRequest): Response | undefined => {
    const path = new URL(request.url, "http://x").pathname;
    if (!path.startsWith("/payments/")) return undefined;
    if (request.method === "GET" && state.failReads) return errorResponse(500, "INTERNAL_ERROR");
    if (request.method === "GET" && path === "/payments/offer") {
      return jsonResponse(200, state.offer);
    }
    if (request.method === "GET" && path === "/payments/status") {
      const current = state.states.length > 1 ? state.states.shift()! : state.states[0];
      return jsonResponse(200, {
        state: current,
        paidAt: current === "paid" ? "2026-10-01T10:05:00Z" : null,
        confirmWaitSeconds: state.confirmWaitSeconds,
      });
    }
    if (request.method === "POST" && path === "/payments/checkout") {
      state.checkouts += 1;
      if (state.checkoutError) {
        return errorResponse(state.checkoutError.status, state.checkoutError.code, {
          details: state.checkoutError.details,
        });
      }
      return jsonResponse(201, { checkoutUrl: state.checkoutUrl });
    }
    return undefined;
  };
}
