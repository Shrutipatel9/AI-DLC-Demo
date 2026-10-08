// "Confirming your payment" (US6.5; AC6.5.1, AC6.5.2, AC6.5.3) and the user-started analysis
// (FR-015: nothing starts by itself; US7.1: AC7.1.1, AC7.1.2).
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import {
  analysisServer,
  newAnalysisState,
  type AnalysisServerState,
} from "@/test-utils/analysis-server";
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

function start(
  state: PaymentsServerState,
  onStartAnalysis?: () => void,
  analysis: AnalysisServerState = newAnalysisState(),
) {
  const requests = mockFetch(paymentsServer(state), analysisServer(analysis));
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
    await waitFor(() => expect(toastMock.success).toHaveBeenCalledWith("Payment confirmed."));
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
    expect(screen.getByTestId("payment-start-analysis-button")).toBeEnabled();
  });

  it("points back to the payment screen when no payment was started", async () => {
    start(newPaymentsState({ states: ["none"] }));
    expect(await screen.findByTestId("payment-not-found")).toBeInTheDocument();
    expect(screen.getByTestId("payment-back-link")).toHaveAttribute("href", "/payment");
  });
});

describe("Starting the analysis (US7.1)", () => {
  const post = (requests: { method: string; url: string }[]) =>
    requests.filter(
      (request) => request.method === "POST" && request.url.endsWith("/analysis/runs"),
    );

  it("starts only on the click, then opens the progress screen (AC7.1.1)", async () => {
    const analysis = newAnalysisState();
    const requests = start(newPaymentsState({ states: ["paid"] }), undefined, analysis);
    const button = await screen.findByTestId("payment-start-analysis-button");
    await waitFor(() => expect(button).toBeEnabled());
    expect(post(requests)).toHaveLength(0); // confirmation alone never starts it (FR-015)

    await userEvent.setup().click(button);

    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/analysis"));
    expect(analysis.starts).toBe(1);
  });

  it("cannot be started twice by clicking again", async () => {
    const analysis = newAnalysisState();
    start(newPaymentsState({ states: ["paid"] }), undefined, analysis);
    const button = await screen.findByTestId("payment-start-analysis-button");
    await waitFor(() => expect(button).toBeEnabled());
    const user = userEvent.setup();
    await user.dblClick(button);
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/analysis"));
    expect(analysis.starts).toBe(1);
  });

  it("shows the 409 message and sends the user to the photo screen (AC7.1.2)", async () => {
    const analysis = newAnalysisState({ start: { status: 409, code: "PHOTO_IDENTITY_MISMATCH" } });
    start(newPaymentsState({ states: ["paid"] }), undefined, analysis);
    const button = await screen.findByTestId("payment-start-analysis-button");
    await waitFor(() => expect(button).toBeEnabled());

    await userEvent.setup().click(button);

    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/photos"));
    expect(toastMock.error).toHaveBeenCalledWith(expect.stringContaining("same person"));
    expect(screen.getByTestId("payment-start-analysis-button")).toBeEnabled();
  });

  it("an incomplete photo set also goes to the photo screen", async () => {
    start(
      newPaymentsState({ states: ["paid"] }),
      undefined,
      newAnalysisState({ start: { status: 409, code: "PHOTO_SET_INCOMPLETE" } }),
    );
    const button = await screen.findByTestId("payment-start-analysis-button");
    await waitFor(() => expect(button).toBeEnabled());
    await userEvent.setup().click(button);
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/photos"));
    expect(toastMock.error).toHaveBeenCalledWith(expect.stringContaining("every angle"));
  });

  it("an analysis that is already complete just opens the progress screen", async () => {
    start(
      newPaymentsState({ states: ["paid"] }),
      undefined,
      newAnalysisState({ start: { status: 409, code: "ANALYSIS_ALREADY_COMPLETE" } }),
    );
    const button = await screen.findByTestId("payment-start-analysis-button");
    await waitFor(() => expect(button).toBeEnabled());
    await userEvent.setup().click(button);
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/analysis"));
    expect(toastMock.error).not.toHaveBeenCalled();
  });

  it("any other failure shows a message and stays on the screen", async () => {
    start(
      newPaymentsState({ states: ["paid"] }),
      undefined,
      newAnalysisState({ start: { status: 402, code: "PAYMENT_REQUIRED" } }),
    );
    const button = await screen.findByTestId("payment-start-analysis-button");
    await waitFor(() => expect(button).toBeEnabled());
    await userEvent.setup().click(button);
    await waitFor(() =>
      expect(toastMock.error).toHaveBeenCalledWith("Please complete your payment first."),
    );
    expect(router.push).not.toHaveBeenCalled();
  });
});
