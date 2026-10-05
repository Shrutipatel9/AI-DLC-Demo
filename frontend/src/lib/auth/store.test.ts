// Auth store, actions and hooks (FE-001, FE-002, BR5.1, BR5.4, AC1.9.1, AC1.9.3).
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { errorResponse, jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";

import * as actions from "./actions";
import { resetSession } from "./session";
import { useAuth, useAuthActions } from "./hooks";
import { resetAuthStore, setSession, signOutOnce, useAuthStore, type User } from "./store";

const USER: User = {
  id: "11111111-1111-4111-8111-111111111111",
  fullName: "Maya Test",
  email: "maya@example.test",
  isVerified: true,
  role: "user",
  memberSince: "2026-10-01T10:00:00Z",
};

const CODE_SENT = {
  maskedEmail: "m•••@example.test",
  expiresAt: "2026-10-01T10:10:00Z",
  resendAvailableAt: "2026-10-01T10:01:00Z",
};

describe("auth store", () => {
  beforeEach(() => {
    resetAuthStore();
    resetSession();
    configureApiOrigin("http://api.test");
  });

  it("starts empty and initializing, as after a page reload (U2 restores the session)", () => {
    expect(useAuthStore.getState()).toMatchObject({
      status: "initializing",
      accessToken: null,
      user: null,
      pending: null,
    });
  });

  it("keeps the session in memory only and never writes Web Storage", () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    setSession("token-1", "2026-10-01T10:15:00Z", USER);
    expect(useAuthStore.getState().accessToken).toBe("token-1");
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    expect(setItem).not.toHaveBeenCalled();
    signOutOnce("logout", useAuthStore.getState().generation);
    expect(useAuthStore.getState().accessToken).toBeNull();
  });

  it("sign-up remembers the code step and verify signs in with that email and purpose", async () => {
    const requests = mockFetch(
      route("POST", "/auth/register", () => jsonResponse(202, CODE_SENT)),
      route("POST", "/auth/verify", () =>
        jsonResponse(200, { accessToken: "tok", expiresAt: "2026-10-01T10:15:00Z", user: USER }),
      ),
    );
    await actions.signUp({
      fullName: "Maya",
      email: " Maya@Example.TEST ",
      password: "Sunrise2026x",
    });
    expect(useAuthStore.getState().pending).toMatchObject({
      email: "maya@example.test",
      purpose: "signup",
      maskedEmail: CODE_SENT.maskedEmail,
    });
    const user = await actions.verifyCode("123456");
    expect(user.fullName).toBe("Maya Test");
    expect(requests[1].body).toEqual({
      email: "maya@example.test",
      code: "123456",
      purpose: "signup",
    });
    expect(useAuthStore.getState()).toMatchObject({ accessToken: "tok", pending: null });
  });

  it("login sets a login code step; verify without a step is refused", async () => {
    mockFetch(route("POST", "/auth/login", () => jsonResponse(202, CODE_SENT)));
    await expect(actions.verifyCode("123456")).rejects.toThrow("No code step");
    await actions.logIn({ email: "maya@example.test", password: "x" });
    expect(useAuthStore.getState().pending?.purpose).toBe("login");
    actions.cancelPending();
    expect(useAuthStore.getState().pending).toBeNull();
  });

  it("loads who-am-I and returns null when the session has ended", async () => {
    expect(await actions.loadCurrentUser()).toBeNull();
    setSession("tok", "2026-10-01T10:15:00Z", USER);
    const requests = mockFetch(
      route("GET", "/auth/me", () => jsonResponse(200, { ...USER, fullName: "Maya Updated" })),
    );
    expect((await actions.loadCurrentUser())?.fullName).toBe("Maya Updated");
    expect(requests[0].headers.authorization).toBe("Bearer tok");
    mockFetch(route("GET", "/auth/me", () => errorResponse(401, "NOT_AUTHENTICATED")));
    expect(await actions.loadCurrentUser()).toBeNull();
  });

  it("rethrows other who-am-I failures", async () => {
    setSession("tok", "2026-10-01T10:15:00Z", USER);
    mockFetch(route("GET", "/auth/me", () => errorResponse(500, "INTERNAL_ERROR")));
    await expect(actions.loadCurrentUser()).rejects.toMatchObject({ code: "INTERNAL_ERROR" });
    expect(useAuthStore.getState().accessToken).toBe("tok");
  });

  it("exposes selectors without the token, and sign-out clears state", () => {
    const { result } = renderHook(() => useAuth());
    expect(result.current.isAuthenticated).toBe(false);
    act(() => setSession("secret-token", "2026-10-01T10:15:00Z", USER));
    expect(result.current).toMatchObject({ isAuthenticated: true, user: USER });
    expect(JSON.stringify(result.current)).not.toContain("secret-token");
    expect(renderHook(() => useAuthActions()).result.current.logout).toBeTypeOf("function");
    act(() => {
      signOutOnce("logout", useAuthStore.getState().generation);
    });
    expect(result.current.isAuthenticated).toBe(false);
  });
});
