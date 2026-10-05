// Forgot password, step 3 (US3.9; AC3.9.3-AC3.9.5; BR4.4, BR4.5, BR5.2, BR7.4).
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import * as actions from "@/lib/auth/actions";
import { resetSession } from "@/lib/auth/session";
import { resetAuthStore, setPending } from "@/lib/auth/store";
import { errorResponse, jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, router, toastMock } from "@/test-utils/next-mocks";

import { ResetPasswordForm } from "./reset-password-form";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

async function withResetToken() {
  setPending({
    email: "maya@example.test",
    maskedEmail: "m•••@example.test",
    purpose: "password_reset",
    expiresAt: "2026-10-01T10:10:00Z",
    resendAvailableAt: "2026-10-01T10:01:00Z",
  });
  mockFetch(() =>
    jsonResponse(200, { resetToken: "reset-token", expiresAt: "2026-10-01T10:10:00Z" }),
  );
  await actions.verifyResetCode("123456");
}

async function fill(password: string, confirm: string) {
  const user = userEvent.setup();
  await user.type(screen.getByTestId("reset-password-new-input"), password);
  await user.type(screen.getByTestId("reset-password-confirm-input"), confirm);
  await user.click(screen.getByTestId("reset-password-submit-button"));
}

describe("ResetPasswordForm", () => {
  beforeEach(async () => {
    resetAuthStore();
    resetSession();
    resetNextMocks();
    configureApiOrigin("http://api.test");
    // Use up any token left by an earlier test.
    mockFetch(() => jsonResponse(204, null));
    if (actions.hasResetToken()) await actions.resetPassword("Moonrise2027y");
  });

  it("without a reset token (for example after a reload) offers to start again", () => {
    render(<ResetPasswordForm />);
    expect(screen.getByTestId("reset-password-start-again-link")).toHaveAttribute(
      "href",
      "/forgot-password",
    );
  });

  it("the confirm field must match before anything is sent", async () => {
    await withResetToken();
    const requests = mockFetch(() => jsonResponse(204, null));
    render(<ResetPasswordForm />);
    await fill("Moonrise2027y", "Moonrise2027z");
    expect(await screen.findByTestId("confirmPassword-error")).toHaveTextContent("don't match");
    expect(requests).toHaveLength(0);
  });

  it("checks the password rule on the client", async () => {
    await withResetToken();
    const requests = mockFetch(() => jsonResponse(204, null));
    render(<ResetPasswordForm />);
    await fill("short", "short");
    expect(await screen.findByTestId("newPassword-error")).toHaveTextContent("rules below");
    expect(requests).toHaveLength(0);
  });

  it("sets the new password and goes to log in with a success toast", async () => {
    await withResetToken();
    const requests = mockFetch(
      route("POST", "/auth/password/reset", () => jsonResponse(204, null)),
    );
    render(<ResetPasswordForm />);
    await fill("Moonrise2027y", "Moonrise2027y");
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/login"));
    expect(requests[0].body).toEqual({ resetToken: "reset-token", newPassword: "Moonrise2027y" });
    expect(toastMock.success).toHaveBeenCalledWith("Password changed — please log in.");
  });

  it("an expired or used token shows the start-again message", async () => {
    await withResetToken();
    mockFetch(() => errorResponse(401, "RESET_TOKEN_INVALID"));
    render(<ResetPasswordForm />);
    await fill("Moonrise2027y", "Moonrise2027y");
    expect(await screen.findByTestId("reset-password-start-again")).toBeInTheDocument();
  });

  it("a server password rejection is shown on the new-password field", async () => {
    await withResetToken();
    mockFetch(() =>
      errorResponse(422, "VALIDATION_FAILED", {
        details: [{ field: "newPassword", reason: "PASSWORD_TOO_WEAK" }],
      }),
    );
    render(<ResetPasswordForm />);
    await fill("Password2026", "Password2026");
    expect(await screen.findByTestId("newPassword-error")).toHaveTextContent("too common");
  });
});
