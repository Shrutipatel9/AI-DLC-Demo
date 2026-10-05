// The payment screen (US6.1, US6.2; AC6.1.1, AC6.1.2, AC6.1.3, AC6.2.1, AC6.2.2, AC6.2.3).
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { mockFetch } from "@/test-utils/fetch-mock";
import { resetNextMocks, router, toastMock } from "@/test-utils/next-mocks";
import {
  TEST_OFFER,
  newPaymentsState,
  paymentsServer,
  type PaymentsServerState,
} from "@/test-utils/payments-server";

import { PaymentScreen } from "./payment-screen";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

function start(state: PaymentsServerState, props: { cancelled?: boolean } = {}) {
  const navigate = vi.fn();
  const requests = mockFetch(paymentsServer(state));
  render(<PaymentScreen navigate={navigate} {...props} />);
  return { navigate, requests };
}

beforeEach(() => {
  resetNextMocks();
  configureApiOrigin("http://api.test");
});

describe("Payment screen (US6.1)", () => {
  it("shows the configured price, what payment unlocks and when analysis starts", async () => {
    start(newPaymentsState());
    expect(await screen.findByTestId("payment-price")).toHaveTextContent("$29.00");
    const includes = screen.getByTestId("payment-includes");
    expect(within(includes).getAllByRole("listitem")).toHaveLength(3);
    expect(includes).toHaveTextContent("11 features");
    expect(includes).toHaveTextContent("AI-generated visuals");
    expect(includes).toHaveTextContent("AI Beauty Assistant");
    expect(screen.getByTestId("payment-start-note")).toHaveTextContent(
      "it starts only when you click Start Analysis",
    );
    expect(screen.getByTestId("payment-pay-button")).toHaveTextContent("Pay $29.00");
    expect(screen.getByTestId("payment-step-label")).toHaveTextContent("Step 4 of 5 · Payment");
    // No result or partial content before payment (AC6.1.1).
    expect(screen.queryByText(/score|result|report preview/i)).not.toBeInTheDocument();
  });

  it("uses whatever price and currency the server is configured with", async () => {
    start(newPaymentsState({ offer: { ...TEST_OFFER, amount: 4500, currency: "EUR" } }));
    expect(await screen.findByTestId("payment-price")).toHaveTextContent("€45.00");
  });

  it("goes to the confirmation screen when the user has already paid", async () => {
    start(newPaymentsState({ states: ["paid"] }));
    await vi.waitFor(() => expect(router.replace).toHaveBeenCalledWith("/payment/success"));
    expect(screen.queryByTestId("payment-pay-button")).not.toBeInTheDocument();
  });

  it("reports a load failure and retries", async () => {
    const state = newPaymentsState({ failReads: true });
    start(state);
    expect(await screen.findByTestId("payment-error")).toBeInTheDocument();
    expect(toastMock.error).toHaveBeenCalled();
    state.failReads = false;
    await userEvent.setup().click(screen.getByTestId("payment-retry-button"));
    expect(await screen.findByTestId("payment-price")).toBeInTheDocument();
  });
});

describe("Pay with hosted Checkout (US6.2)", () => {
  it("sends the browser to the hosted Checkout URL from the server", async () => {
    const state = newPaymentsState();
    const { navigate } = start(state);
    await userEvent.setup().click(await screen.findByTestId("payment-pay-button"));
    await vi.waitFor(() =>
      expect(navigate).toHaveBeenCalledWith("https://checkout.example.test/c/pay/cs_test_1"),
    );
    expect(state.checkouts).toBe(1);
    expect(screen.getByTestId("payment-pay-button")).toBeDisabled();
    expect(screen.getByTestId("payment-pay-button")).toHaveTextContent("Opening secure checkout");
  });

  it("explains a photo mismatch and links back to the photos (AC6.2.2)", async () => {
    const { navigate } = start(
      newPaymentsState({
        checkoutError: {
          status: 409,
          code: "PHOTO_IDENTITY_MISMATCH",
          details: [{ angle: "left_3q", reason: "IDENTITY_MISMATCH" }],
        },
      }),
    );
    await userEvent.setup().click(await screen.findByTestId("payment-pay-button"));
    const problem = await screen.findByTestId("payment-problem");
    expect(problem).toHaveTextContent("don't appear to show the same person");
    expect(screen.getByTestId("payment-photos-link")).toHaveAttribute("href", "/photos");
    expect(toastMock.error).toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
    expect(screen.getByTestId("payment-pay-button")).toBeEnabled();
  });

  it("says nothing was charged when the payment service is down", async () => {
    start(newPaymentsState({ checkoutError: { status: 502, code: "UPSTREAM_UNAVAILABLE" } }));
    await userEvent.setup().click(await screen.findByTestId("payment-pay-button"));
    expect(await screen.findByTestId("payment-problem")).toHaveTextContent(
      "You have not been charged",
    );
    expect(screen.queryByTestId("payment-photos-link")).not.toBeInTheDocument();
  });

  it("moves on to the confirmation when checkout says it is already paid", async () => {
    start(newPaymentsState({ checkoutError: { status: 409, code: "ALREADY_PAID" } }));
    await userEvent.setup().click(await screen.findByTestId("payment-pay-button"));
    await vi.waitFor(() => expect(router.replace).toHaveBeenCalledWith("/payment/success"));
  });

  it("says nothing was charged after a cancelled checkout (AC6.2.3)", async () => {
    start(newPaymentsState(), { cancelled: true });
    expect(await screen.findByTestId("payment-cancelled-notice")).toHaveTextContent(
      "You have not been charged",
    );
    expect(screen.getByTestId("payment-pay-button")).toBeEnabled();
  });
});
