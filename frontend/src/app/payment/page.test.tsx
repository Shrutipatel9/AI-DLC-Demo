// The /payment, /payment/success and /payment/cancel routes: protected like every signed-in
// page, then the payment screens (US6.1, US6.2, US6.5).
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { resetSession } from "@/lib/auth/session";
import { resetAuthStore, setSession, signOutOnce, useAuthStore, type User } from "@/lib/auth/store";
import { jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, router } from "@/test-utils/next-mocks";
import { newPaymentsState, paymentsServer } from "@/test-utils/payments-server";

import PaymentCancelPage from "./cancel/page";
import PaymentPage from "./page";
import PaymentSuccessPage from "./success/page";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

const USER: User = {
  id: "u-1",
  fullName: "Maya Test",
  email: "maya@example.test",
  isVerified: true,
  role: "user",
  memberSince: "2026-10-01T10:00:00Z",
};

describe("payment pages", () => {
  beforeEach(() => {
    resetAuthStore();
    resetSession();
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("wait for the session and send a signed-out visitor to log in", () => {
    render(<PaymentPage />);
    expect(screen.getByTestId("session-loader")).toBeInTheDocument();
    act(() => {
      signOutOnce("session_expired", useAuthStore.getState().generation);
    });
    expect(router.replace).toHaveBeenCalledWith("/login");
  });

  it("show the payment screen, the cancelled notice and the confirmation to a signed-in user", async () => {
    act(() => setSession("tok", "2026-10-01T10:15:00Z", USER));
    mockFetch(
      route("GET", "/auth/me", () => jsonResponse(200, USER)),
      paymentsServer(newPaymentsState({ states: ["pending"] })),
    );
    const first = render(<PaymentPage />);
    expect(await screen.findByTestId("payment-price")).toBeInTheDocument();
    first.unmount();

    const second = render(<PaymentCancelPage />);
    expect(await screen.findByTestId("payment-cancelled-notice")).toBeInTheDocument();
    second.unmount();

    render(<PaymentSuccessPage />);
    expect(await screen.findByText("Confirming your payment")).toBeInTheDocument();
  });
});
