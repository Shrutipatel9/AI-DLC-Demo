// Code entry (US3.2; AC3.2.1-AC3.2.3, AC3.2.6; OtpEntry spec).
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import {
  resetAuthStore,
  setPending,
  setSession,
  useAuthStore,
  type CodePurpose,
} from "@/lib/auth/store";
import { errorResponse, jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, router } from "@/test-utils/next-mocks";

import { messageFor, retryClock } from "./messages";
import { VerifyForm } from "./verify-form";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

function startStep(purpose: CodePurpose = "signup") {
  setPending({
    email: "maya@example.test",
    maskedEmail: "m•••@example.test",
    purpose,
    expiresAt: "2026-10-01T10:10:00Z",
    resendAvailableAt: "2026-10-01T10:01:00Z",
  });
}

async function enter(code: string) {
  const user = userEvent.setup();
  await user.type(screen.getByTestId("verify-code-input"), code);
  await user.click(screen.getByTestId("verify-submit-button"));
}

describe("VerifyForm", () => {
  beforeEach(() => {
    resetAuthStore();
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("routes to log in when there is no code step (e.g. after a reload)", () => {
    render(<VerifyForm />);
    expect(router.replace).toHaveBeenCalledWith("/login");
  });

  it("shows the masked address and a numeric one-time-code field", async () => {
    startStep();
    render(<VerifyForm />);
    expect(screen.getByTestId("verify-masked-email")).toHaveTextContent("m•••@example.test");
    const input = screen.getByTestId("verify-code-input");
    expect(input).toHaveAttribute("inputmode", "numeric");
    expect(input).toHaveAttribute("autocomplete", "one-time-code");
    await waitFor(() => expect(input).toHaveFocus());
  });

  it("signs in and goes home on the right code", async () => {
    startStep();
    mockFetch(
      route("POST", "/auth/verify", () =>
        jsonResponse(200, {
          accessToken: "tok",
          expiresAt: "2026-10-01T10:15:00Z",
          user: {
            id: "u",
            fullName: "Maya",
            email: "maya@example.test",
            isVerified: true,
            role: "user",
            memberSince: "2026-10-01T10:00:00Z",
          },
        }),
      ),
    );
    render(<VerifyForm />);
    await enter("123456");
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/home"));
    expect(useAuthStore.getState().accessToken).toBe("tok");
    // No bounce through the login page while the next step is opened: the loader stays up,
    // and the next step is opened once.
    expect(router.replace).not.toHaveBeenCalledWith("/login");
    expect(screen.getByTestId("page-loader")).toHaveTextContent("Signing you in…");
    expect(router.push).toHaveBeenCalledTimes(1);
  });

  it("sends a signed-in visitor with no code step to their next step, not to log in", async () => {
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
        jsonResponse(200, { step: "photos", flaggedAngles: [] }),
      ),
    );
    render(<VerifyForm />);
    expect(screen.getByTestId("page-loader")).toBeInTheDocument();
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/photos"));
    expect(router.replace).not.toHaveBeenCalledWith("/login");
  });

  it("shows tries left for a wrong code and requires six digits", async () => {
    startStep("login");
    mockFetch(() =>
      errorResponse(401, "CODE_INVALID", {
        details: [{ reason: "CODE_INVALID", attemptsLeft: 3 }],
      }),
    );
    render(<VerifyForm />);
    await enter("12");
    expect(await screen.findByTestId("code-error")).toHaveTextContent("6-digit code");
    await userEvent.setup().type(screen.getByTestId("verify-code-input"), "3456");
    await userEvent.setup().click(screen.getByTestId("verify-submit-button"));
    await waitFor(() =>
      expect(screen.getByTestId("code-error")).toHaveTextContent(
        "That code isn't right. 3 tries left.",
      ),
    );
  });

  it("offers a new code when the code expired (U2 replaces U1's start-again link)", async () => {
    startStep();
    mockFetch(() => errorResponse(401, "CODE_EXPIRED"));
    render(<VerifyForm />);
    await enter("123456");
    expect(await screen.findByTestId("code-error")).toHaveTextContent("This code has expired.");
    expect(screen.queryByTestId("verify-start-again-link")).toBeNull();
    expect(screen.getByTestId("resend-code-button")).toBeInTheDocument();
    expect(screen.getByTestId("verify-go-back-link")).toHaveAttribute(
      "href",
      "/signup?email=maya%40example.test",
    );
  });

  it("disables verify while locked and explains when to retry", async () => {
    startStep();
    mockFetch(() => errorResponse(429, "CODE_LOCKED", { headers: { "Retry-After": "900" } }));
    render(<VerifyForm />);
    await enter("123456");
    expect(await screen.findByTestId("verify-locked-reason")).toBeInTheDocument();
    expect(screen.getByTestId("verify-submit-button")).toBeDisabled();
    expect(screen.getByTestId("code-error")).toHaveTextContent(
      "Too many tries. You can try again at",
    );
  });
});

describe("messages", () => {
  it("formats the retry clock and singular tries", () => {
    const now = new Date("2026-10-01T10:00:00");
    expect(retryClock(900, now)).toMatch(/10:15/);
    const error = { code: "CODE_INVALID", attemptsLeft: 1 } as never;
    expect(messageFor(error)).toBe("That code isn't right. 1 try left.");
    expect(messageFor({ code: "SOMETHING" } as never)).toMatch(/Something went wrong/);
    expect(messageFor({ code: "TIMEOUT" } as never)).toMatch(/too long/);
    expect(messageFor({ code: "NETWORK_ERROR" } as never)).toMatch(/couldn't reach/);
    expect(messageFor({ code: "CODE_RESEND_COOLDOWN", retryAfterSeconds: 30 } as never)).toMatch(
      /30 seconds/,
    );
  });
});
