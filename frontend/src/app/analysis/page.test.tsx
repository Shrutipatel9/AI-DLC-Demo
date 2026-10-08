// The /analysis route: protected like every signed-in page, then the progress screen (US7.2).
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { resetSession } from "@/lib/auth/session";
import { resetAuthStore, setSession, signOutOnce, useAuthStore, type User } from "@/lib/auth/store";
import { WRITING, analysisServer, newAnalysisState } from "@/test-utils/analysis-server";
import { jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, router } from "@/test-utils/next-mocks";

import AnalysisPage from "./page";

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

describe("analysis page", () => {
  beforeEach(() => {
    resetAuthStore();
    resetSession();
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("waits for the session and sends a signed-out visitor to log in", () => {
    render(<AnalysisPage />);
    expect(screen.getByTestId("session-loader")).toBeInTheDocument();
    act(() => {
      signOutOnce("session_expired", useAuthStore.getState().generation);
    });
    expect(router.replace).toHaveBeenCalledWith("/login");
  });

  it("shows the progress screen to a signed-in user", async () => {
    act(() => setSession("tok", "2026-10-01T10:15:00Z", USER));
    mockFetch(
      route("GET", "/auth/me", () => jsonResponse(200, USER)),
      analysisServer(newAnalysisState({ runs: [WRITING] })),
    );
    render(<AnalysisPage />);
    expect(await screen.findByTestId("analysis-progress")).toBeInTheDocument();
    expect(screen.getByTestId("analysis-step-writing-state")).toHaveTextContent("In progress");
  });
});
