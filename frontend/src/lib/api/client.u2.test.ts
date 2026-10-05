// API client 401 handling (FE-005, FE-006; BR6.3, BR6.4; NFR2.15): only NOT_AUTHENTICATED
// triggers the shared refresh, a request is retried at most once, and the raw path used by
// refresh and logout never triggers it.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { errorResponse, jsonResponse, mockFetch } from "@/test-utils/fetch-mock";

import {
  apiRaw,
  apiRequest,
  configureApiOrigin,
  setTokenProvider,
  setUnauthorizedHandler,
} from "./client";
import { ApiError } from "./errors";

describe("API client 401 handling (U2)", () => {
  let token: string | null;

  beforeEach(() => {
    configureApiOrigin("http://api.test");
    token = "old";
    setTokenProvider(() => token);
  });

  afterEach(() => {
    setUnauthorizedHandler(null);
    setTokenProvider(() => null);
  });

  it("refreshes after NOT_AUTHENTICATED and retries once with the new token", async () => {
    const handler = vi.fn(async () => {
      token = "new";
    });
    setUnauthorizedHandler(handler);
    const requests = mockFetch((request) =>
      request.headers.authorization === "Bearer new"
        ? jsonResponse(200, { ok: true })
        : errorResponse(401, "NOT_AUTHENTICATED"),
    );
    await expect(apiRequest("/data", { method: "POST", body: { a: 1 } })).resolves.toEqual({
      ok: true,
    });
    expect(handler).toHaveBeenCalledTimes(1);
    expect(requests).toHaveLength(2);
    expect(requests[1].body).toEqual({ a: 1 });
  });

  it.each([
    "INVALID_CREDENTIALS",
    "CODE_INVALID",
    "CODE_EXPIRED",
    "RESET_TOKEN_INVALID",
    "SESSION_INVALID",
  ])("does not refresh on 401 %s", async (code) => {
    const handler = vi.fn(async () => undefined);
    setUnauthorizedHandler(handler);
    mockFetch(() => errorResponse(401, code));
    await expect(apiRequest("/x")).rejects.toMatchObject({ status: 401, code });
    expect(handler).not.toHaveBeenCalled();
  });

  it("the raw path (refresh, logout) never triggers a refresh and sends the CSRF header", async () => {
    const handler = vi.fn(async () => undefined);
    setUnauthorizedHandler(handler);
    const requests = mockFetch(() => errorResponse(401, "NOT_AUTHENTICATED"));
    await expect(
      apiRaw("/auth/refresh", { method: "POST", headers: { "X-Refresh-Attempt": "a".repeat(22) } }),
    ).rejects.toBeInstanceOf(ApiError);
    expect(handler).not.toHaveBeenCalled();
    expect(requests[0].headers["x-refresh-attempt"]).toBe("a".repeat(22));
    expect(requests[0].headers["x-requested-with"]).toBe("XMLHttpRequest");
    expect(requests[0].credentials).toBe("include");
  });

  it("a failed refresh is what the original request reports", async () => {
    const refused = new ApiError({ status: 401, code: "SESSION_INVALID", message: "ended" });
    setUnauthorizedHandler(async () => {
      throw refused;
    });
    mockFetch(() => errorResponse(401, "NOT_AUTHENTICATED"));
    await expect(apiRequest("/x")).rejects.toBe(refused);
  });

  it("without a registered handler the 401 is returned as it is", async () => {
    mockFetch(() => errorResponse(401, "NOT_AUTHENTICATED"));
    await expect(apiRequest("/x")).rejects.toMatchObject({ code: "NOT_AUTHENTICATED" });
  });
});
