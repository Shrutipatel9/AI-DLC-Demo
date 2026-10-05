// Protected placeholder page (AC3.8.1; U2: ProtectedRoute, the user menu with a confirmed
// logout; BR3.2, BR6.1). U1's "an empty store after a reload goes to login" is replaced by
// session restore (WF-U2-2): a reload shows the loader until restore finishes.
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmDialogHost } from "@/components/feedback/confirm-dialog";
import { configureApiOrigin } from "@/lib/api/client";
import { resetSession } from "@/lib/auth/session";
import { resetAuthStore, setSession, signOutOnce, useAuthStore, type User } from "@/lib/auth/store";
import { errorResponse, jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, router, toastMock } from "@/test-utils/next-mocks";

import HomePage from "./page";

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

describe("HomePage", () => {
  beforeEach(() => {
    resetAuthStore();
    resetSession();
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("shows the session loader while restoring and goes to log in once signed out", () => {
    render(<HomePage />);
    expect(screen.getByTestId("session-loader")).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalled();
    act(() => {
      signOutOnce("session_expired", useAuthStore.getState().generation);
    });
    expect(router.replace).toHaveBeenCalledWith("/login");
  });

  it("greets the user by name from who-am-I, and logs out after confirming", async () => {
    act(() => setSession("tok", "2026-10-01T10:15:00Z", USER));
    const requests = mockFetch(
      route("GET", "/auth/me", () => jsonResponse(200, { ...USER, fullName: "Maya Fresh" })),
      route("POST", "/auth/logout", () => jsonResponse(204, null)),
    );
    render(
      <>
        <HomePage />
        <ConfirmDialogHost />
      </>,
    );
    expect(await screen.findByText("Hi, Maya Fresh")).toBeInTheDocument();
    expect(screen.getByTestId("user-menu-name")).toHaveTextContent("Maya Fresh");
    const user = userEvent.setup();
    await user.click(screen.getByTestId("user-menu-button"));
    await user.click(screen.getByTestId("user-menu-logout"));
    expect(screen.getByTestId("confirm-dialog")).toHaveTextContent("Log out?");
    await user.click(screen.getByTestId("confirm-dialog-confirm"));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/login"));
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(requests.some((r) => r.url.endsWith("/auth/logout"))).toBe(true);
    expect(toastMock.success).toHaveBeenCalledWith("You're logged out.");
  });

  it("keeps the user signed in when the logout is cancelled", async () => {
    act(() => setSession("tok", "2026-10-01T10:15:00Z", USER));
    mockFetch(route("GET", "/auth/me", () => jsonResponse(200, USER)));
    render(
      <>
        <HomePage />
        <ConfirmDialogHost />
      </>,
    );
    const user = userEvent.setup();
    await user.click(await screen.findByTestId("user-menu-button"));
    await user.click(screen.getByTestId("user-menu-logout"));
    await user.click(screen.getByTestId("confirm-dialog-cancel"));
    expect(screen.queryByTestId("confirm-dialog")).toBeNull();
    expect(useAuthStore.getState().status).toBe("signedIn");
    expect(screen.getByTestId("user-menu-button")).toHaveFocus();
  });

  it("keeps the session and reports other failures in a toast", async () => {
    act(() => setSession("tok", "2026-10-01T10:15:00Z", USER));
    mockFetch(route("GET", "/auth/me", () => errorResponse(500, "INTERNAL_ERROR")));
    render(<HomePage />);
    await waitFor(() => expect(toastMock.error).toHaveBeenCalled());
    expect(screen.getByTestId("home-greeting")).toHaveTextContent("Hi, Maya Test");
  });

  it("links to the questionnaire until it is submitted (U3)", async () => {
    act(() => setSession("tok", "2026-10-01T10:15:00Z", USER));
    let given = false;
    let submitted = false;
    mockFetch(
      route("GET", "/auth/me", () => jsonResponse(200, USER)),
      route("GET", "/onboarding/consent", () =>
        jsonResponse(200, {
          consentTextVersion: "consent-v1",
          consentText: "t",
          agreementText: "a",
          given,
        }),
      ),
      route("GET", "/onboarding/response", () =>
        jsonResponse(200, {
          answers: { q1: { value: "Designer" } },
          visibleQuestionIds: ["q1"],
          submitted,
        }),
      ),
    );
    const { unmount } = render(<HomePage />);
    const link = await screen.findByText("Start your questionnaire");
    expect(link).toHaveAttribute("href", "/onboarding");
    expect(link).toHaveAttribute("data-testid", "home-onboarding-link");
    unmount();

    given = true;
    const second = render(<HomePage />);
    expect(await screen.findByText("Continue your questionnaire")).toBeInTheDocument();
    second.unmount();

    submitted = true;
    render(<HomePage />);
    expect(await screen.findByTestId("home-status")).toHaveTextContent(
      "Your questionnaire is submitted. Next, add your photos.",
    );
    expect(screen.queryByTestId("home-onboarding-link")).toBeNull();
    // U4: the photo step is linked once the questionnaire is submitted (temporary until U10).
    expect(screen.getByTestId("home-photos-link")).toHaveAttribute("href", "/photos");
  });

  it("still offers the questionnaire when its status cannot be read", async () => {
    act(() => setSession("tok", "2026-10-01T10:15:00Z", USER));
    mockFetch(
      route("GET", "/auth/me", () => jsonResponse(200, USER)),
      route("GET", "/onboarding/consent", () => errorResponse(500, "INTERNAL_ERROR")),
    );
    render(<HomePage />);
    expect(await screen.findByText("Go to your questionnaire")).toBeInTheDocument();
  });
});
