// The /report and /chat routes: protected like every signed-in page.
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatPage from "@/app/chat/page";
import { configureApiOrigin } from "@/lib/api/client";
import { resetSession } from "@/lib/auth/session";
import { resetAuthStore, setSession, signOutOnce, useAuthStore, type User } from "@/lib/auth/store";
import { jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, router } from "@/test-utils/next-mocks";
import { newReportState, reportServer } from "@/test-utils/report-server";

import ReportPage from "./page";

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

describe("report and chat pages", () => {
  beforeEach(() => {
    resetAuthStore();
    resetSession();
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("sends a signed-out visitor to log in", () => {
    render(<ReportPage />);
    expect(screen.getByTestId("session-loader")).toBeInTheDocument();
    act(() => {
      signOutOnce("session_expired", useAuthStore.getState().generation);
    });
    expect(router.replace).toHaveBeenCalledWith("/login");
  });

  it("shows the report to a signed-in user", async () => {
    act(() => setSession("tok", "2026-10-01T10:15:00Z", USER));
    mockFetch(
      route("GET", "/auth/me", () => jsonResponse(200, USER)),
      reportServer(newReportState()),
    );
    render(<ReportPage />);
    expect(await screen.findByTestId("report")).toBeInTheDocument();
    expect(screen.getByTestId("nav-report")).toBeInTheDocument();
  });

  it("opens the Chat placeholder from the header link", async () => {
    act(() => setSession("tok", "2026-10-01T10:15:00Z", USER));
    mockFetch(route("GET", "/auth/me", () => jsonResponse(200, USER)));
    render(<ChatPage />);
    expect(await screen.findByTestId("chat-placeholder")).toHaveTextContent("coming soon");
  });
});
