// Sign-up form (US3.1; AC3.1.1, AC3.1.2, AC3.1.4; BR1.1, BR1.2).
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { resetAuthStore, useAuthStore } from "@/lib/auth/store";
import { errorResponse, jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, router, searchParams, toastMock } from "@/test-utils/next-mocks";

import { SignUpForm } from "./signup-form";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

const CODE_SENT = {
  maskedEmail: "m•••@example.test",
  expiresAt: "2026-10-01T10:10:00Z",
  resendAvailableAt: "2026-10-01T10:01:00Z",
};

async function fill(values: { name?: string; email?: string; password?: string }) {
  const user = userEvent.setup();
  if (values.name !== undefined)
    await user.type(screen.getByTestId("signup-fullname-input"), values.name);
  if (values.email !== undefined)
    await user.type(screen.getByTestId("signup-email-input"), values.email);
  if (values.password !== undefined)
    await user.type(screen.getByTestId("signup-password-input"), values.password);
  return user;
}

describe("SignUpForm", () => {
  beforeEach(() => {
    resetAuthStore();
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("shows the password rules before typing and ticks them live", async () => {
    render(<SignUpForm />);
    expect(screen.getByTestId("password-rule-length")).toHaveAttribute("data-met", "false");
    await fill({ password: "abc12345" });
    expect(screen.getByTestId("password-rule-length")).toHaveAttribute("data-met", "true");
    expect(screen.getByTestId("password-rule-letter-number")).toHaveAttribute("data-met", "true");
  });

  it("validates inline before sending anything", async () => {
    const requests = mockFetch();
    render(<SignUpForm />);
    const user = await fill({ email: "nope", password: "short" });
    await user.click(screen.getByTestId("signup-submit-button"));
    expect(await screen.findByText("Enter your full name.")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByTestId("signup-email-input")).toHaveAttribute("aria-invalid", "true");
    expect(requests).toHaveLength(0);
  });

  it("registers, remembers the code step and goes to /verify", async () => {
    const requests = mockFetch(route("POST", "/auth/register", () => jsonResponse(202, CODE_SENT)));
    render(<SignUpForm />);
    const user = await fill({
      name: "Maya Test",
      email: "maya@example.test",
      password: "Sunrise2026x",
    });
    await user.click(screen.getByTestId("signup-submit-button"));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/verify"));
    expect(requests[0].body).toEqual({
      fullName: "Maya Test",
      email: "maya@example.test",
      password: "Sunrise2026x",
    });
    expect(useAuthStore.getState().pending?.maskedEmail).toBe(CODE_SENT.maskedEmail);
    expect(toastMock.success).toHaveBeenCalled();
  });

  it("offers sign-in when the email is already registered", async () => {
    mockFetch(() => errorResponse(409, "EMAIL_ALREADY_REGISTERED"));
    render(<SignUpForm />);
    const user = await fill({ name: "Maya", email: "maya@example.test", password: "Sunrise2026x" });
    await user.click(screen.getByTestId("signup-submit-button"));
    expect(await screen.findByTestId("signup-signin-instead-link")).toHaveAttribute(
      "href",
      "/login",
    );
    expect(screen.getByTestId("email-error")).toHaveTextContent("already exists");
  });

  it("maps a server PASSWORD_TOO_WEAK to the password field", async () => {
    mockFetch(() =>
      errorResponse(422, "VALIDATION_FAILED", {
        details: [{ field: "password", reason: "PASSWORD_TOO_WEAK" }],
      }),
    );
    render(<SignUpForm />);
    const user = await fill({ name: "Maya", email: "maya@example.test", password: "Password1" });
    await user.click(screen.getByTestId("signup-submit-button"));
    expect(await screen.findByTestId("password-error")).toHaveTextContent("too common");
  });

  it("shows a toast for email delivery failures and prefills the email from the URL", async () => {
    searchParams.value = new URLSearchParams("email=again%40example.test");
    mockFetch(() => errorResponse(502, "UPSTREAM_UNAVAILABLE"));
    render(<SignUpForm />);
    expect(screen.getByTestId("signup-email-input")).toHaveValue("again@example.test");
    const user = await fill({ name: "Maya", password: "Sunrise2026x" });
    await user.click(screen.getByTestId("signup-password-toggle-button"));
    expect(screen.getByTestId("signup-password-input")).toHaveAttribute("type", "text");
    await user.click(screen.getByTestId("signup-submit-button"));
    await waitFor(() =>
      expect(toastMock.error).toHaveBeenCalledWith("We couldn't send the email. Please try again."),
    );
  });
});
