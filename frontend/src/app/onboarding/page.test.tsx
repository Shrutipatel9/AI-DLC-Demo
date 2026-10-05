// The /onboarding page is protected (BR6.1) and opens on the consent step (US4.1).
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { resetSession } from "@/lib/auth/session";
import { resetAuthStore, setSession, signOutOnce, useAuthStore, type User } from "@/lib/auth/store";
import { mockFetch } from "@/test-utils/fetch-mock";
import { resetNextMocks, router } from "@/test-utils/next-mocks";
import { newState, onboardingServer } from "@/test-utils/onboarding-server";

import OnboardingPage from "./page";

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

describe("OnboardingPage", () => {
  beforeEach(() => {
    resetAuthStore();
    resetSession();
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("sends a signed-out visitor to log in", () => {
    render(<OnboardingPage />);
    act(() => {
      signOutOnce("session_expired", useAuthStore.getState().generation);
    });
    expect(router.replace).toHaveBeenCalledWith("/login");
  });

  it("shows the consent step with the bearer token sent to the API", async () => {
    act(() => setSession("tok", "2099-01-01T00:15:00Z", USER));
    const requests = mockFetch(onboardingServer(newState()));
    render(<OnboardingPage />);
    expect(await screen.findByTestId("consent-step")).toBeInTheDocument();
    expect(requests[0].headers.authorization).toBe("Bearer tok");
    expect(requests[0].credentials).toBe("include");
  });
});
