// "Send a new code" countdown (US3.3; AC3.3.1, AC3.3.3; BR1.1, BR1.3; WF-U2-1).
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { resetSession } from "@/lib/auth/session";
import { resetAuthStore, setPending } from "@/lib/auth/store";
import { errorResponse, jsonResponse, mockFetch } from "@/test-utils/fetch-mock";
import { resetNextMocks, toastMock } from "@/test-utils/next-mocks";

import { ResendCodeButton } from "./resend-code-button";

vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

const T0 = new Date("2026-10-01T10:00:00Z").getTime();
const iso = (ms: number) => new Date(ms).toISOString();

function renderButton(availableInMs = 60_000) {
  setPending({
    email: "maya@example.test",
    maskedEmail: "m•••@example.test",
    purpose: "login",
    expiresAt: iso(T0 + 600_000),
    resendAvailableAt: iso(T0 + availableInMs),
  });
  const onResent = vi.fn();
  render(<ResendCodeButton availableAt={iso(T0 + availableInMs)} onResent={onResent} />);
  return { button: screen.getByTestId("resend-code-button"), onResent };
}

async function click(button: HTMLElement) {
  await act(async () => {
    button.click();
    await Promise.resolve();
  });
  await act(async () => {
    await vi.runOnlyPendingTimersAsync();
  });
}

describe("ResendCodeButton", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(T0);
    resetAuthStore();
    resetSession();
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("counts down and stays disabled until the resend time", () => {
    const { button } = renderButton();
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent("Send a new code in 1:00");
    act(() => {
      vi.advanceTimersByTime(59_000);
    });
    expect(button).toHaveTextContent("Send a new code in 0:01");
    expect(button).toBeDisabled();
  });

  it("becomes available by itself when the countdown ends", () => {
    const { button } = renderButton();
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(button).toBeEnabled();
    expect(button).toHaveTextContent(/^Send a new code$/);
  });

  it("sends a new code, confirms it and lets the form clear the field", async () => {
    const { button, onResent } = renderButton(0);
    mockFetch(() =>
      jsonResponse(202, {
        maskedEmail: "m•••@example.test",
        expiresAt: iso(T0 + 600_000),
        resendAvailableAt: iso(T0 + 60_000),
      }),
    );
    await click(button);
    expect(onResent).toHaveBeenCalledTimes(1);
    expect(toastMock.success).toHaveBeenCalledWith("We sent a new code. Check your email.");
  });

  it("re-syncs the countdown when the server says to wait", async () => {
    const { button } = renderButton(0);
    mockFetch(() =>
      errorResponse(429, "CODE_RESEND_COOLDOWN", { headers: { "Retry-After": "30" } }),
    );
    await click(button);
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent(/Send a new code in 0:(30|29)/);
  });

  it("during a lockout says when to try again", async () => {
    const { button } = renderButton(0);
    mockFetch(() => errorResponse(429, "CODE_LOCKED", { headers: { "Retry-After": "900" } }));
    await click(button);
    expect(button).toHaveTextContent(/Try again in 1[45]:\d\d/);
    expect(toastMock.error).toHaveBeenCalledWith(expect.stringMatching(/^Too many tries/));
  });
});
