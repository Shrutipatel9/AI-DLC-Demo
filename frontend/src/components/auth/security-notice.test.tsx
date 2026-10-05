// Sign-out notice on /login (BR6.7; AC3.6.4; FD post-review R-03, R-07) and the
// development-only session logger (NFR5.11).
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { sessionLog } from "@/lib/auth/session-log";
import { resetAuthStore, setSignedOutReason } from "@/lib/auth/store";

import { SecurityNotice } from "./security-notice";

describe("SecurityNotice", () => {
  beforeEach(() => resetAuthStore());

  it("explains a sign-out for security in plain language", () => {
    act(() => setSignedOutReason("security"));
    render(<SecurityNotice />);
    expect(screen.getByTestId("security-notice")).toHaveTextContent(
      "You were signed out for your security. Please log in again.",
    );
  });

  it("explains a password change and an ended session", () => {
    act(() => setSignedOutReason("password_changed"));
    const { unmount } = render(<SecurityNotice />);
    expect(screen.getByTestId("security-notice")).toHaveTextContent("Your password was changed.");
    unmount();
    act(() => setSignedOutReason("session_expired"));
    render(<SecurityNotice />);
    expect(screen.getByTestId("security-notice")).toHaveTextContent("Your session ended.");
  });

  it("shows nothing after a normal logout or with no sign-out", () => {
    act(() => setSignedOutReason("logout"));
    const { unmount } = render(<SecurityNotice />);
    expect(screen.queryByTestId("security-notice")).toBeNull();
    unmount();
    act(() => setSignedOutReason(null));
    render(<SecurityNotice />);
    expect(screen.queryByTestId("security-notice")).toBeNull();
  });
});

describe("sessionLog", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("writes to the console in development only and never in production", () => {
    const info = vi.spyOn(console, "info").mockImplementation(() => undefined);
    vi.stubEnv("NODE_ENV", "production");
    sessionLog("signed-out", "security");
    expect(info).not.toHaveBeenCalled();
    vi.stubEnv("NODE_ENV", "development");
    sessionLog("lock-mode", "locks");
    expect(info).toHaveBeenCalledWith("[session] lock-mode: locks");
  });
});
