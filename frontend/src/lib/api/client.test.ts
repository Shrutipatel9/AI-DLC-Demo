// API client (FE-004, BR5.2, AC1.9.2, NFR5.11).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { errorResponse, jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";

import { apiRequest, configureApiOrigin, getApiOrigin, setTokenProvider } from "./client";
import { ApiError, isApiError, normaliseCode } from "./errors";

describe("apiRequest", () => {
  beforeEach(() => {
    configureApiOrigin("http://api.test/");
    setTokenProvider(() => null);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("sends credentials, X-Requested-With and JSON headers to the configured origin", async () => {
    const requests = mockFetch(route("POST", "/auth/login", () => jsonResponse(202, { ok: true })));
    const result = await apiRequest<{ ok: boolean }>("/auth/login", {
      method: "POST",
      body: { email: "a@b.co" },
    });
    expect(result).toEqual({ ok: true });
    expect(getApiOrigin()).toBe("http://api.test");
    const [request] = requests;
    expect(request.url).toBe("http://api.test/auth/login");
    expect(request.credentials).toBe("include");
    expect(request.headers["x-requested-with"]).toBe("XMLHttpRequest");
    expect(request.headers["content-type"]).toBe("application/json");
    expect(request.body).toEqual({ email: "a@b.co" });
    expect(request.headers.authorization).toBeUndefined();
  });

  it("attaches the bearer token from the registered provider", async () => {
    setTokenProvider(() => "token-abc");
    const requests = mockFetch(route("GET", "/auth/me", () => jsonResponse(200, { id: "u" })));
    await apiRequest("/auth/me");
    expect(requests[0].headers.authorization).toBe("Bearer token-abc");
    expect(requests[0].method).toBe("GET");
  });

  it("maps the C11 envelope to ApiError with code, details, request id and Retry-After", async () => {
    mockFetch(
      route("POST", "/auth/verify", () =>
        errorResponse(401, "CODE_INVALID", {
          details: [{ reason: "CODE_INVALID", attemptsLeft: 3 }],
          requestId: "rid-1",
          headers: { "Retry-After": "42" },
        }),
      ),
    );
    const error = await apiRequest("/auth/verify", { method: "POST", body: {} }).catch((e) => e);
    expect(isApiError(error)).toBe(true);
    expect(error).toMatchObject({ status: 401, code: "CODE_INVALID", requestId: "rid-1" });
    expect((error as ApiError).attemptsLeft).toBe(3);
    expect((error as ApiError).retryAfterSeconds).toBe(42);
  });

  it("falls back to the X-Request-ID header and treats unknown codes as INTERNAL_ERROR", async () => {
    mockFetch(
      () => new Response("not json", { status: 500, headers: { "X-Request-ID": "hdr-9" } }),
    );
    const error = (await apiRequest("/x").catch((e) => e)) as ApiError;
    expect(error.code).toBe("INTERNAL_ERROR");
    expect(error.requestId).toBe("hdr-9");
    expect(normaliseCode("SOMETHING_NEW")).toBe("INTERNAL_ERROR");
    expect(normaliseCode("RATE_LIMITED")).toBe("RATE_LIMITED");
  });

  it("exposes field errors from VALIDATION_FAILED", async () => {
    mockFetch(() =>
      errorResponse(422, "VALIDATION_FAILED", {
        details: [{ field: "password", reason: "PASSWORD_TOO_WEAK" }, { reason: "NO_FIELD" }],
      }),
    );
    const error = (await apiRequest("/auth/register", { method: "POST", body: {} }).catch(
      (e) => e,
    )) as ApiError;
    expect(error.fieldErrors).toEqual({ password: "PASSWORD_TOO_WEAK" });
    expect(error.attemptsLeft).toBeNull();
  });

  it("turns a network failure into NETWORK_ERROR", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))),
    );
    const error = (await apiRequest("/auth/me").catch((e) => e)) as ApiError;
    expect(error.code).toBe("NETWORK_ERROR");
    expect(error.status).toBe(0);
  });

  it("aborts after the timeout with TIMEOUT", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_input: unknown, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError")),
            );
          }),
      ),
    );
    const pending = apiRequest("/auth/me", { timeoutMs: 30_000 }).catch((e) => e);
    await vi.advanceTimersByTimeAsync(30_000);
    const error = (await pending) as ApiError;
    expect(error.code).toBe("TIMEOUT");
  });

  it("returns undefined for 204 and never touches Web Storage", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    mockFetch(() => jsonResponse(204, null));
    await expect(apiRequest("/auth/logout", { method: "POST" })).resolves.toBeUndefined();
    expect(setItem).not.toHaveBeenCalled();
  });

  it("follows an external abort signal", async () => {
    const controller = new AbortController();
    controller.abort();
    mockFetch(() => jsonResponse(200, {}));
    const error = (await apiRequest("/auth/me", { signal: controller.signal }).catch(
      (e) => e,
    )) as ApiError;
    expect(error.code).toBe("NETWORK_ERROR");
  });
});
