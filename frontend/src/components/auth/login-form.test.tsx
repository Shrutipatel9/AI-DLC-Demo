// Login form, step 1 (US3.4; AC3.4.1, AC3.4.2).
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { resetAuthStore, setSession, useAuthStore } from "@/lib/auth/store";
import { errorResponse, jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, router, toastMock } from "@/test-utils/next-mocks";

import { LogInForm } from "./login-form";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

async function submit(email: string, password: string) {
  const user = userEvent.setup();
  if (email) await user.type(screen.getByTestId("login-email-input"), email);
  if (password) await user.type(screen.getByTestId("login-password-input"), password);
  await user.click(screen.getByTestId("login-submit-button"));
}

describe("LogInForm", () => {
  beforeEach(() => {
    resetAuthStore();
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("sends an already signed-in visitor to their next step behind the loader", async () => {
    setSession("tok", "2099-01-01T00:00:00Z", {
      id: "u",
      fullName: "Maya",
      email: "maya@example.test",
      isVerified: true,
      role: "user",
      memberSince: "2026-10-01T10:00:00Z",
    });
    mockFetch(
      route("GET", "/journey/next-step", () =>
        jsonResponse(200, { step: "payment", flaggedAngles: [] }),
      ),
    );
    render(<LogInForm />);
    expect(screen.getByTestId("page-loader")).toBeInTheDocument();
    expect(screen.queryByTestId("login-form")).toBeNull();
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/payment"));
  });

  it("requires email and password", async () => {
    const requests = mockFetch();
    render(<LogInForm />);
    await submit("", "");
    expect(await screen.findByText("Enter your password.")).toBeInTheDocument();
    expect(requests).toHaveLength(0);
  });

  it("sends the code and moves to /verify without any token", async () => {
    mockFetch(
      route("POST", "/auth/login", () =>
        jsonResponse(202, {
          maskedEmail: "m•••@example.test",
          expiresAt: "2026-10-01T10:10:00Z",
          resendAvailableAt: "2026-10-01T10:01:00Z",
        }),
      ),
    );
    render(<LogInForm />);
    await submit("maya@example.test", "Sunrise2026x");
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/verify"));
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().pending?.purpose).toBe("login");
  });

  it("shows the generic credentials message", async () => {
    mockFetch(() => errorResponse(401, "INVALID_CREDENTIALS"));
    render(<LogInForm />);
    await submit("maya@example.test", "wrong");
    expect(await screen.findByTestId("login-form-error")).toHaveTextContent(
      "Email or password is incorrect.",
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("explains rate limiting in a toast", async () => {
    mockFetch(() => errorResponse(429, "RATE_LIMITED", { headers: { "Retry-After": "60" } }));
    render(<LogInForm />);
    await submit("maya@example.test", "Sunrise2026x");
    await waitFor(() =>
      expect(toastMock.error).toHaveBeenCalledWith(
        "Too many attempts. Please wait a minute and try again.",
      ),
    );
  });

  it("explains a lock with the time it ends", async () => {
    mockFetch(() => errorResponse(429, "CODE_LOCKED", { headers: { "Retry-After": "900" } }));
    render(<LogInForm />);
    await submit("maya@example.test", "Sunrise2026x");
    await waitFor(() =>
      expect(toastMock.error).toHaveBeenCalledWith(expect.stringMatching(/^Too many tries/)),
    );
  });
});
