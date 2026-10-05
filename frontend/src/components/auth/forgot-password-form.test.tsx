// Forgot password, step 1 (US3.9; AC3.9.1, AC11.7.1; BR4.1, BR7.4).
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { resetSession } from "@/lib/auth/session";
import { resetAuthStore, useAuthStore } from "@/lib/auth/store";
import { errorResponse, jsonResponse, mockFetch } from "@/test-utils/fetch-mock";
import { resetNextMocks, router, toastMock } from "@/test-utils/next-mocks";

import { ForgotPasswordForm } from "./forgot-password-form";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

const SENT = {
  maskedEmail: "m•••@example.test",
  expiresAt: "2026-10-01T10:10:00Z",
  resendAvailableAt: "2026-10-01T10:01:00Z",
};

async function submit(email: string) {
  const user = userEvent.setup();
  if (email) await user.type(screen.getByTestId("forgot-password-email-input"), email);
  await user.click(screen.getByTestId("forgot-password-submit-button"));
}

describe("ForgotPasswordForm", () => {
  beforeEach(() => {
    resetAuthStore();
    resetSession();
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("requires an email, shown next to the field", async () => {
    render(<ForgotPasswordForm />);
    await submit("");
    const error = await screen.findByTestId("email-error");
    expect(error).toHaveTextContent("Enter your email address.");
    const input = screen.getByTestId("forgot-password-email-input");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", "email-error");
  });

  it("refuses a malformed email without calling the server", async () => {
    const requests = mockFetch(() => jsonResponse(202, SENT));
    render(<ForgotPasswordForm />);
    await submit("not-an-email");
    expect(await screen.findByTestId("email-error")).toHaveTextContent("valid email");
    expect(requests).toHaveLength(0);
  });

  it("moves to the code step with no outcome toast", async () => {
    const requests = mockFetch(() => jsonResponse(202, SENT));
    render(<ForgotPasswordForm />);
    await submit("Maya@Example.test");
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/forgot-password/verify"));
    expect(requests[0].body).toEqual({ email: "Maya@Example.test" });
    expect(toastMock.success).not.toHaveBeenCalled();
    expect(useAuthStore.getState().pending).toMatchObject({
      email: "maya@example.test",
      purpose: "password_reset",
    });
  });

  it("behaves the same whatever the email (the server answers the same)", async () => {
    mockFetch(() => jsonResponse(202, { ...SENT, maskedEmail: "n•••@example.test" }));
    render(<ForgotPasswordForm />);
    await submit("nobody@example.test");
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/forgot-password/verify"));
    expect(toastMock.success).not.toHaveBeenCalled();
  });

  it("reports throttling in an error toast", async () => {
    mockFetch(() => errorResponse(429, "RATE_LIMITED", { headers: { "Retry-After": "60" } }));
    render(<ForgotPasswordForm />);
    await submit("maya@example.test");
    await waitFor(() =>
      expect(toastMock.error).toHaveBeenCalledWith(
        "Too many attempts. Please wait a minute and try again.",
      ),
    );
    expect(router.push).not.toHaveBeenCalled();
  });

  it("links back to log in", () => {
    render(<ForgotPasswordForm />);
    expect(screen.getByTestId("forgot-password-login-link")).toHaveAttribute("href", "/login");
  });
});
