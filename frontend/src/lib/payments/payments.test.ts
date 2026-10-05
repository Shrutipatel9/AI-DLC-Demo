// Payment helpers: the API functions through the single client, price formatting, the checkout
// redirect guard and the confirmation polling hook (US6.1, US6.2, US6.5; FR7.3, FR7.4).
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { errorResponse, mockFetch } from "@/test-utils/fetch-mock";
import { newPaymentsState, paymentsServer } from "@/test-utils/payments-server";

import {
  formatPrice,
  getOffer,
  getPaymentStatus,
  goToCheckout,
  isCheckoutUrl,
  startCheckout,
  usePaymentConfirmation,
} from ".";

beforeEach(() => {
  configureApiOrigin("http://api.test");
});

describe("payment API functions", () => {
  it("read the offer and status and start checkout through the API client", async () => {
    const state = newPaymentsState({ states: ["pending"] });
    const requests = mockFetch(paymentsServer(state));

    expect((await getOffer()).amount).toBe(2900);
    expect((await getPaymentStatus()).state).toBe("pending");
    expect(await startCheckout()).toBe("https://checkout.example.test/c/pay/cs_test_1");

    expect(requests.map((r) => `${r.method} ${r.url}`)).toEqual([
      "GET http://api.test/payments/offer",
      "GET http://api.test/payments/status",
      "POST http://api.test/payments/checkout",
    ]);
    expect(requests.every((r) => r.headers["x-requested-with"] === "XMLHttpRequest")).toBe(true);
  });

  it("surfaces a 409 from checkout as an ApiError with its code", async () => {
    mockFetch(
      paymentsServer(
        newPaymentsState({
          checkoutError: { status: 409, code: "PHOTO_IDENTITY_MISMATCH", details: [] },
        }),
      ),
    );
    await expect(startCheckout()).rejects.toMatchObject({ code: "PHOTO_IDENTITY_MISMATCH" });
  });
});

describe("formatPrice", () => {
  it("formats minor units with the currency's own decimals", () => {
    expect(formatPrice(2900, "USD", "en-US")).toBe("$29.00");
    expect(formatPrice(1999, "EUR", "en-US")).toBe("€19.99");
    expect(formatPrice(2900, "JPY", "en-US")).toBe("¥2,900");
  });

  it("falls back to a plain amount for an unknown currency code", () => {
    expect(formatPrice(2900, "??", "en-US")).toBe("29.00 ??");
  });
});

describe("checkout redirect", () => {
  it("accepts only absolute http(s) URLs", () => {
    expect(isCheckoutUrl("https://checkout.stripe.com/c/pay/cs_1")).toBe(true);
    expect(isCheckoutUrl("http://localhost:8000/payments/fake-checkout/cs_fake_1")).toBe(true);
    expect(isCheckoutUrl("javascript:alert(1)")).toBe(false);
    expect(isCheckoutUrl("/relative")).toBe(false);
  });

  it("refuses to navigate to anything else", () => {
    expect(() => goToCheckout("javascript:alert(1)")).toThrow("not valid");
  });

  it("navigates the whole window to a valid checkout URL", () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    goToCheckout("https://checkout.stripe.com/c/pay/cs_1");
    expect(assign).toHaveBeenCalledWith("https://checkout.stripe.com/c/pay/cs_1");
  });
});

describe("usePaymentConfirmation", () => {
  it("polls until the server reports paid, then stops", async () => {
    const state = newPaymentsState({ states: ["pending", "pending", "paid"] });
    const requests = mockFetch(paymentsServer(state));
    const { result } = renderHook(() => usePaymentConfirmation(5));
    expect(result.current.phase).toBe("loading");
    await waitFor(() => expect(result.current.phase).toBe("paid"));
    const polls = requests.length;
    expect(polls).toBe(3);
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(requests.length).toBe(polls); // no polling after paid
    expect(result.current.waitedTooLong).toBe(false);
  });

  it("says it waited too long after the configured wait, and keeps polling", async () => {
    const state = newPaymentsState({ states: ["pending"], confirmWaitSeconds: 0 });
    const requests = mockFetch(paymentsServer(state));
    const { result } = renderHook(() => usePaymentConfirmation(5));
    await waitFor(() => expect(result.current.waitedTooLong).toBe(true));
    expect(result.current.phase).toBe("pending");
    await waitFor(() => expect(requests.length).toBeGreaterThan(2));
  });

  it("keeps the last state when a poll fails and tries again", async () => {
    let calls = 0;
    const state = newPaymentsState({ states: ["paid"] });
    const server = paymentsServer(state);
    mockFetch((request) => {
      calls += 1;
      return calls === 1 ? errorResponse(500, "INTERNAL_ERROR") : server(request);
    });
    const { result } = renderHook(() => usePaymentConfirmation(5));
    await waitFor(() => expect(result.current.phase).toBe("paid"));
    expect(calls).toBe(2);
  });
});
