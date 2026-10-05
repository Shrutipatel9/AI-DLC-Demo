// ProtectedRoute, FullPageLoader and AuthBootstrap (BR6.1, BR6.5; WF-U2-2; AC3.5.1).
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { resetSession } from "@/lib/auth/session";
import {
  resetAuthStore,
  setRestoreFailed,
  setSession,
  signOutOnce,
  useAuthStore,
  type User,
} from "@/lib/auth/store";
import { errorResponse, jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, router } from "@/test-utils/next-mocks";

import { AuthBootstrap } from "./auth-bootstrap";
import { ProtectedRoute } from "./protected-route";

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

function page() {
  return render(
    <ProtectedRoute>
      <p data-testid="secret-page">Signed-in content</p>
    </ProtectedRoute>,
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    resetAuthStore();
    resetSession();
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("shows an accessible loader while the session is restored, never the login form", () => {
    page();
    const loader = screen.getByTestId("session-loader");
    expect(loader).toHaveAttribute("role", "status");
    expect(loader).toHaveTextContent("Restoring your session");
    expect(screen.queryByTestId("secret-page")).toBeNull();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("offers Retry when the server could not be reached", async () => {
    act(() => setRestoreFailed(true));
    page();
    expect(screen.getByTestId("session-restore-error")).toHaveTextContent("couldn't reach");
    mockFetch(
      route("POST", "/auth/refresh", () =>
        jsonResponse(200, { accessToken: "t", expiresAt: "2099-01-01T00:00:00Z" }),
      ),
      route("GET", "/auth/me", () => jsonResponse(200, USER)),
    );
    await userEvent.setup().click(screen.getByTestId("session-retry-button"));
    expect(await screen.findByTestId("secret-page")).toBeInTheDocument();
  });

  it("sends a signed-out visitor to log in", () => {
    act(() => {
      signOutOnce("session_expired", useAuthStore.getState().generation);
    });
    page();
    expect(router.replace).toHaveBeenCalledWith("/login");
  });

  it("renders the page once signed in", () => {
    act(() => setSession("tok", "2099-01-01T00:00:00Z", USER));
    page();
    expect(screen.getByTestId("secret-page")).toBeInTheDocument();
  });
});

describe("AuthBootstrap", () => {
  beforeEach(() => {
    resetAuthStore();
    resetSession();
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("restores the session once on mount", async () => {
    const requests = mockFetch(
      route("POST", "/auth/refresh", () =>
        errorResponse(401, "SESSION_INVALID", { details: [{ reason: "INVALID" }] }),
      ),
    );
    render(<AuthBootstrap />);
    await waitFor(() => expect(useAuthStore.getState().status).toBe("signedOut"));
    expect(requests).toHaveLength(1);
  });
});
