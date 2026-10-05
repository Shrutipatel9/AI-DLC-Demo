// "Confirming your payment" (US6.5; AC6.5.1, AC6.5.2, AC6.5.3) and the user-started analysis
// (FR-015: nothing starts by itself).
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { mockFetch } from "@/test-utils/fetch-mock";
import { resetNextMocks, router, toastMock } from "@/test-utils/next-mocks";
import {
  newPaymentsState,
  paymentsServer,
  type PaymentsServerState,
} from "@/test-utils/payments-server";

import { PaymentConfirmation } from "./payment-confirmation";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

function start(state: PaymentsServerState, onStartAnalysis?: () => void) {
  const requests = mockFetch(paymentsServer(state));
  render(<PaymentConfirmation pollIntervalMs={5} onStartAnalysis={onStartAnalysis} />);
  return requests;
}

beforeEach(() => {
  resetNextMocks();
  configureApiOrigin("http://api.test");
});

describe("Confirming the payment (US6.5)", () => {
  it("shows confirming, with Start Analysis unavailable, before the webhook (AC6.5.1)", async () => {
    start(newPaymentsState({ states: ["pending"] }));
    expect(await screen.findByTestId("payment-confirmation-title")).toHaveTextContent(
      "Confirming your payment",
    );
    const startButton = screen.getByTestId("payment-start-analysis-button");
    expect(startButton).toBeDisabled();
    expect(startButton).toHaveAccessibleDescription("Available once your payment is confirmed.");
    expect(screen.getByTestId("payment-announcement")).toHaveTextContent("");
    expect(screen.queryByTestId("payment-still-confirming")).not.toBeInTheDocument();
  });

  it("updates without a reload and announces the confirmation (AC6.5.2)", async () => {
    const onStart = vi.fn();
    start(newPaymentsState({ states: ["pending", "pending", "paid"] }), onStart);
    expect(await screen.findByText("Confirming your payment")).toBeInTheDocument();
    expect(await screen.findByText("Payment confirmed")).toBeInTheDocument();
    expect(screen.getByTestId("payment-announcement")).toHaveTextContent(
      "Your payment is confirmed. You can start your analysis.",
    );
    expect(screen.getByTestId("payment-announcement")).toHaveAttribute("aria-live", "polite");
    expect(toastMock.success).toHaveBeenCalledWith("Payment confirmed.");
    const startButton = screen.getByTestId("payment-start-analysis-button");
    expect(startButton).toBeEnabled();
    expect(onStart).not.toHaveBeenCalled(); // never starts by itself
    await userEvent.setup().click(startButton);
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("says the payment is still being confirmed after the configured wait (AC6.5.3)", async () => {
    start(newPaymentsState({ states: ["pending"], confirmWaitSeconds: 0 }));
    const notice = await screen.findByTestId("payment-still-confirming");
    expect(notice).toHaveTextContent("still being confirmed");
    expect(notice).toHaveTextContent("You won't be charged twice");
    expect(notice).toHaveTextContent("safely leave this page and come back later");
    expect(screen.getByTestId("payment-start-analysis-button")).toBeDisabled();
  });

  it("an already confirmed payment shows Start Analysis without a toast", async () => {
    start(newPaymentsState({ states: ["paid"] }));
    expect(await screen.findByText("Payment confirmed")).toBeInTheDocument();
    expect(toastMock.success).not.toHaveBeenCalled();
    await userEvent.setup().click(screen.getByTestId("payment-start-analysis-button"));
    expect(router.push).toHaveBeenCalledWith("/home"); // until U6 adds the analysis start
  });

  it("points back to the payment screen when no payment was started", async () => {
    start(newPaymentsState({ states: ["none"] }));
    expect(await screen.findByTestId("payment-not-found")).toBeInTheDocument();
    expect(screen.getByTestId("payment-back-link")).toHaveAttribute("href", "/payment");
  });
});
