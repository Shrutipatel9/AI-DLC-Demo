// Auth store and session with the real coordinator (fetch mocked beneath it): restore,
// logout, password flows, and no Web Storage (WF-U2-2, WF-U2-6, WF-U2-7, WF-U2-8; BR6.1,
// BR6.5, BR6.7, BR6.8; AC3.5.1, AC3.5.2, AC3.5.5, AC3.7.2, AC11.5.1; NFR2.14, NFR5.1).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { errorResponse, jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";

import * as actions from "./actions";
import { getCoordinator, resetSession, setSessionNotifier } from "./session";
import { resetAuthStore, setSession, useAuthStore, type User } from "./store";
import { fakeBroadcast, fakeLocks, type FakeBroadcastHub } from "./test-utils";

const USER: User = {
  id: "11111111-1111-4111-8111-111111111111",
  fullName: "Maya Test",
  email: "maya@example.test",
  isVerified: true,
  role: "user",
  memberSince: "2026-10-01T10:00:00Z",
};
const TOKEN = { accessToken: "fresh-token", expiresAt: "2099-01-01T00:15:00Z" };
const CODE_SENT = {
  maskedEmail: "m•••@example.test",
  expiresAt: "2099-01-01T00:10:00Z",
  resendAvailableAt: "2099-01-01T00:01:00Z",
};

describe("auth store with session restore (U2)", () => {
  let hub: FakeBroadcastHub;
  const notifier = { error: vi.fn(), navigate: vi.fn() };

  beforeEach(() => {
    resetAuthStore();
    hub = fakeBroadcast();
    resetSession({ locks: fakeLocks(), openChannel: (name) => hub.open(name) });
    notifier.error.mockReset();
    notifier.navigate.mockReset();
    setSessionNotifier(notifier);
    configureApiOrigin("http://api.test");
  });

  afterEach(() => {
    resetSession();
  });

  // ------------------------------------------------------------------- restore (WF-U2-2)

  it("restores a session: refresh, then who-am-I, then signed in", async () => {
    const requests = mockFetch(
      route("POST", "/auth/refresh", () => jsonResponse(200, TOKEN)),
      route("GET", "/auth/me", () => jsonResponse(200, USER)),
    );
    expect(useAuthStore.getState().status).toBe("initializing");
    await actions.restore();
    expect(useAuthStore.getState()).toMatchObject({
      status: "signedIn",
      accessToken: "fresh-token",
      user: USER,
    });
    const refresh = requests[0];
    expect(refresh.headers["x-requested-with"]).toBe("XMLHttpRequest");
    expect(refresh.headers["x-refresh-attempt"]).toMatch(/^[A-Za-z0-9_-]{22}$/);
    expect(refresh.credentials).toBe("include");
    expect(requests[1].headers.authorization).toBe("Bearer fresh-token");
  });

  it("a reused or revoked session signs out with the security notice", async () => {
    mockFetch(
      route("POST", "/auth/refresh", () =>
        errorResponse(401, "SESSION_INVALID", { details: [{ reason: "REUSE_DETECTED" }] }),
      ),
    );
    await actions.restore();
    expect(useAuthStore.getState()).toMatchObject({
      status: "signedOut",
      signedOutReason: "security",
    });
    expect(notifier.navigate).not.toHaveBeenCalled(); // protected pages redirect themselves
  });

  it("a first-time visitor (no cookie) is signed out with no notice", async () => {
    mockFetch(
      route("POST", "/auth/refresh", () =>
        errorResponse(401, "SESSION_INVALID", { details: [{ reason: "INVALID" }] }),
      ),
    );
    await actions.restore();
    expect(useAuthStore.getState()).toMatchObject({ status: "signedOut", signedOutReason: null });
  });

  it("network errors and 5xx keep restoring with a Retry, never sign out", async () => {
    let calls = 0;
    mockFetch(
      route("POST", "/auth/refresh", () => {
        calls += 1;
        return calls <= 2 ? errorResponse(503, "UPSTREAM_UNAVAILABLE") : jsonResponse(200, TOKEN);
      }),
      route("GET", "/auth/me", () => jsonResponse(200, USER)),
    );
    await actions.restore();
    expect(useAuthStore.getState()).toMatchObject({ status: "initializing", restoreFailed: true });
    expect(calls).toBe(2); // one retry with the same attempt id
    expect(notifier.error).not.toHaveBeenCalled(); // the loader shows its own message
    await actions.restore();
    expect(useAuthStore.getState()).toMatchObject({ status: "signedIn", restoreFailed: false });
  });

  it("stays restoring when who-am-I fails after a successful refresh (R-05)", async () => {
    mockFetch(
      route("POST", "/auth/refresh", () => jsonResponse(200, TOKEN)),
      route("GET", "/auth/me", () => errorResponse(500, "INTERNAL_ERROR")),
    );
    await actions.restore();
    expect(useAuthStore.getState()).toMatchObject({ status: "initializing", restoreFailed: true });
  });

  // ------------------------------------------------------------------- logout (WF-U2-6)

  it("logout revokes on the server, tells the other tabs and clears this tab", async () => {
    setSession("tok", TOKEN.expiresAt, USER);
    const otherTab = hub.open("auth");
    const heard: unknown[] = [];
    otherTab.addEventListener("message", (event) => heard.push(event.data));
    const requests = mockFetch(route("POST", "/auth/logout", () => jsonResponse(204, null)));
    await actions.logout();
    await Promise.resolve();
    expect(requests[0].headers["x-requested-with"]).toBe("XMLHttpRequest");
    expect(requests[0].credentials).toBe("include");
    expect(useAuthStore.getState()).toMatchObject({
      status: "signedOut",
      accessToken: null,
      signedOutReason: "logout",
    });
    expect(heard).toContainEqual({ type: "signedOut", reason: "logout" });
    expect(notifier.navigate).not.toHaveBeenCalled(); // the menu routes to /login itself
  });

  it("a logout in another tab signs this tab out and goes to log in once", async () => {
    setSession("tok", TOKEN.expiresAt, USER);
    getCoordinator();
    const otherTab = hub.open("auth");
    otherTab.postMessage({ type: "signedOut", reason: "logout" });
    otherTab.postMessage({ type: "signedOut", reason: "logout" });
    await vi.waitFor(() => expect(useAuthStore.getState().status).toBe("signedOut"));
    expect(notifier.navigate).toHaveBeenCalledTimes(1);
    expect(notifier.navigate).toHaveBeenCalledWith("/login");
  });

  // ------------------------------------------------- reset and change (WF-U2-7, WF-U2-8)

  it("reset keeps the reset token out of the store and away from UI code", async () => {
    mockFetch(
      route("POST", "/auth/password/forgot", () => jsonResponse(202, CODE_SENT)),
      route("POST", "/auth/password/verify-code", () =>
        jsonResponse(200, { resetToken: "reset-secret-token", expiresAt: TOKEN.expiresAt }),
      ),
      route("POST", "/auth/password/reset", () => jsonResponse(204, null)),
    );
    await actions.requestPasswordReset(" Maya@Example.TEST ");
    expect(useAuthStore.getState().pending).toMatchObject({
      email: "maya@example.test",
      purpose: "password_reset",
    });
    await actions.verifyResetCode("123456");
    expect(actions.hasResetToken()).toBe(true);
    expect(JSON.stringify(useAuthStore.getState())).not.toContain("reset-secret-token");
    await actions.resetPassword("Moonrise2027y");
    expect(actions.hasResetToken()).toBe(false);
    await expect(actions.resetPassword("Moonrise2027y")).rejects.toMatchObject({
      code: "RESET_TOKEN_INVALID",
    });
  });

  it("change password keeps this tab signed in by refreshing once", async () => {
    setSession("tok", TOKEN.expiresAt, USER);
    const requests = mockFetch(
      route("POST", "/auth/change-password", () => jsonResponse(204, null)),
      route("POST", "/auth/refresh", () => jsonResponse(200, TOKEN)),
    );
    await actions.changePassword("Sunrise2026x", "Moonrise2027y");
    expect(requests.map((r) => new URL(r.url).pathname)).toEqual([
      "/auth/change-password",
      "/auth/refresh",
    ]);
    expect(useAuthStore.getState()).toMatchObject({
      status: "signedIn",
      accessToken: "fresh-token",
    });
  });

  it("if the refresh after a change is refused, the tab signs out with the password notice", async () => {
    setSession("tok", TOKEN.expiresAt, USER);
    mockFetch(
      route("POST", "/auth/change-password", () => jsonResponse(204, null)),
      route("POST", "/auth/refresh", () =>
        errorResponse(401, "SESSION_INVALID", { details: [{ reason: "REVOKED" }] }),
      ),
    );
    await expect(actions.changePassword("Sunrise2026x", "Moonrise2027y")).rejects.toMatchObject({
      code: "SESSION_INVALID",
    });
    expect(useAuthStore.getState()).toMatchObject({
      status: "signedOut",
      signedOutReason: "password_changed",
    });
  });

  it("resend updates the countdown of the current code step", async () => {
    useAuthStore.setState({
      pending: { email: "maya@example.test", purpose: "login", ...CODE_SENT },
    });
    const later = { ...CODE_SENT, resendAvailableAt: "2099-01-01T00:02:00Z" };
    const requests = mockFetch(route("POST", "/auth/resend-code", () => jsonResponse(202, later)));
    await actions.resendCode();
    expect(requests[0].body).toEqual({ email: "maya@example.test", purpose: "login" });
    expect(useAuthStore.getState().pending?.resendAvailableAt).toBe("2099-01-01T00:02:00Z");
  });

  // ------------------------------------------------------------ no Web Storage (NFR2.14)

  it("never writes Web Storage across restore, refresh and two-tab use", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    mockFetch(
      route("POST", "/auth/refresh", () => jsonResponse(200, TOKEN)),
      route("GET", "/auth/me", () => jsonResponse(200, USER)),
    );
    await actions.restore();
    await getCoordinator().refresh();
    hub.open("auth").postMessage({
      type: "refreshed",
      accessToken: "from-other-tab",
      expiresAt: "2099-01-01T01:00:00Z",
      user: USER,
    });
    await vi.waitFor(() => expect(useAuthStore.getState().accessToken).toBe("from-other-tab"));
    expect(setItem).not.toHaveBeenCalled();
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it("the broadcast carries tokens and profile only, never the refresh cookie", async () => {
    mockFetch(
      route("POST", "/auth/refresh", () => jsonResponse(200, TOKEN)),
      route("GET", "/auth/me", () => jsonResponse(200, USER)),
    );
    setSession("tok", TOKEN.expiresAt, USER);
    await getCoordinator().refresh();
    const refreshed = hub.posted.find(
      (message) => (message as { type: string }).type === "refreshed",
    ) as Record<string, unknown>;
    expect(Object.keys(refreshed).sort()).toEqual(["accessToken", "expiresAt", "type", "user"]);
  });
});
