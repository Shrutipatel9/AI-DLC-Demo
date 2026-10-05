// Settings -> Password (US11.5; AC11.5.1-AC11.5.3; BR5.1-BR5.3, BR6.4, BR7.4; FD R-03).
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { resetSession } from "@/lib/auth/session";
import { resetAuthStore, setSession, useAuthStore, type User } from "@/lib/auth/store";
import { errorResponse, jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, router, toastMock } from "@/test-utils/next-mocks";

import { ChangePasswordForm } from "./change-password-form";

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
const TOKEN = { accessToken: "fresh", expiresAt: "2099-01-01T00:15:00Z" };

async function fill(current: string, next: string, confirm = next) {
  const user = userEvent.setup();
  await user.type(screen.getByTestId("change-password-current-input"), current);
  await user.type(screen.getByTestId("change-password-new-input"), next);
  await user.type(screen.getByTestId("change-password-confirm-input"), confirm);
  await user.click(screen.getByTestId("change-password-submit-button"));
}

describe("ChangePasswordForm", () => {
  beforeEach(() => {
    resetAuthStore();
    resetSession();
    resetNextMocks();
    configureApiOrigin("http://api.test");
    act(() => setSession("tok", TOKEN.expiresAt, USER));
  });

  it("the confirm field must match; nothing is sent otherwise", async () => {
    const requests = mockFetch(() => jsonResponse(204, null));
    render(<ChangePasswordForm />);
    await fill("Sunrise2026x", "Moonrise2027y", "Moonrise2027z");
    expect(await screen.findByTestId("confirmPassword-error")).toHaveTextContent("don't match");
    expect(requests).toHaveLength(0);
  });

  it("changes the password, stays signed in, clears the form and confirms", async () => {
    const requests = mockFetch(
      route("POST", "/auth/change-password", () => jsonResponse(204, null)),
      route("POST", "/auth/refresh", () => jsonResponse(200, TOKEN)),
    );
    render(<ChangePasswordForm />);
    await fill("Sunrise2026x", "Moonrise2027y");
    await waitFor(() => expect(toastMock.success).toHaveBeenCalled());
    expect(requests[0].body).toEqual({
      currentPassword: "Sunrise2026x",
      newPassword: "Moonrise2027y",
    });
    expect(requests[0].headers.authorization).toBe("Bearer tok");
    expect(useAuthStore.getState().status).toBe("signedIn");
    expect(screen.getByTestId("change-password-current-input")).toHaveValue("");
  });

  it("a wrong current password is shown on that field with an error toast, never a refresh", async () => {
    const requests = mockFetch(() => errorResponse(401, "INVALID_CREDENTIALS"));
    render(<ChangePasswordForm />);
    await fill("Wrong2026x", "Moonrise2027y");
    expect(await screen.findByTestId("currentPassword-error")).toHaveTextContent(
      "Your current password is incorrect.",
    );
    expect(toastMock.error).toHaveBeenCalledWith("Your current password is incorrect.");
    expect(requests.map((r) => new URL(r.url).pathname)).toEqual(["/auth/change-password"]);
    expect(useAuthStore.getState().status).toBe("signedIn");
  });

  it("a weak new password from the server is shown on the new-password field", async () => {
    mockFetch(() =>
      errorResponse(422, "VALIDATION_FAILED", {
        details: [{ field: "newPassword", reason: "PASSWORD_TOO_WEAK" }],
      }),
    );
    render(<ChangePasswordForm />);
    await fill("Sunrise2026x", "Password2026");
    expect(await screen.findByTestId("newPassword-error")).toHaveTextContent("too common");
  });

  it("if this session was not kept, the user goes to log in with the password notice", async () => {
    mockFetch(
      route("POST", "/auth/change-password", () => jsonResponse(204, null)),
      route("POST", "/auth/refresh", () =>
        errorResponse(401, "SESSION_INVALID", { details: [{ reason: "REVOKED" }] }),
      ),
    );
    render(<ChangePasswordForm />);
    await fill("Sunrise2026x", "Moonrise2027y");
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/login"));
    expect(useAuthStore.getState().signedOutReason).toBe("password_changed");
  });

  it("other failures are reported in an error toast", async () => {
    mockFetch(() => errorResponse(429, "RATE_LIMITED", { headers: { "Retry-After": "60" } }));
    render(<ChangePasswordForm />);
    await fill("Sunrise2026x", "Moonrise2027y");
    await waitFor(() =>
      expect(toastMock.error).toHaveBeenCalledWith(
        "Too many attempts. Please wait a minute and try again.",
      ),
    );
  });
});
