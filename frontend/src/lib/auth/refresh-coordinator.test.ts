// Refresh coordinator (test-first; FE-005, FE-006, ADR-006).
//
// US3.5, US3.10, US3.11: AC3.5.1, AC3.5.2, AC3.10.1-AC3.10.5, AC3.11.1. Rules BR6.1-BR6.6
// with FD post-review R-02, R-04, R-07 and NFD post-review R-08; NFR5.1-NFR5.5, NFR5.8.
// Fake timers, an in-memory server, and fake `navigator.locks` / `BroadcastChannel`.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  apiRequest,
  configureApiOrigin,
  setTokenProvider,
  setUnauthorizedHandler,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { errorResponse, jsonResponse, mockFetch } from "@/test-utils/fetch-mock";

import {
  ADOPT_WINDOW_MS,
  CLAIM_CAP_MS,
  createRefreshCoordinator,
  newAttemptId,
  reasonFor,
  REFRESH_TIMEOUT_MS,
  type CoordinatorDeps,
  type RefreshCoordinator,
  type SignOutReason,
  type TokenPair,
} from "./refresh-coordinator";
import type { User } from "./store";
import { fakeBroadcast, fakeLocks, type FakeBroadcastHub, type FakeLocks } from "./test-utils";

const T0 = new Date("2026-10-01T10:00:00Z").getTime();
const USER: User = {
  id: "11111111-1111-4111-8111-111111111111",
  fullName: "Maya Test",
  email: "maya@example.test",
  isVerified: true,
  role: "user",
  memberSince: "2026-10-01T10:00:00Z",
};

function iso(ms: number): string {
  return new Date(ms).toISOString();
}

function sessionError(reason: string): ApiError {
  return new ApiError({
    status: 401,
    code: "SESSION_INVALID",
    message: "Your session has ended.",
    details: [{ reason }],
  });
}

function networkError(): ApiError {
  return new ApiError({ status: 0, code: "NETWORK_ERROR", message: "offline" });
}

function serverError(): ApiError {
  return new ApiError({ status: 502, code: "UPSTREAM_UNAVAILABLE", message: "down" });
}

/** The fake API: each refresh call waits until the test settles it. */
class FakeServer {
  calls: { attemptId: string; settle: (outcome: TokenPair | ApiError) => void }[] = [];
  logouts = 0;
  logoutFails = false;
  private counter = 0;

  refresh = (attemptId: string, signal: AbortSignal): Promise<TokenPair> =>
    new Promise((resolve, reject) => {
      signal.addEventListener("abort", () =>
        reject(new ApiError({ status: 0, code: "TIMEOUT", message: "timed out" })),
      );
      this.calls.push({
        attemptId,
        settle: (outcome) => (outcome instanceof ApiError ? reject(outcome) : resolve(outcome)),
      });
    });

  /** Answer the newest pending call with a fresh 15-minute token. */
  succeed(index = this.calls.length - 1): TokenPair {
    this.counter += 1;
    const pair = { accessToken: `token-${this.counter}`, expiresAt: iso(Date.now() + 15 * 60_000) };
    this.calls.at(index)?.settle(pair);
    return pair;
  }

  fail(error: ApiError, index = this.calls.length - 1): void {
    this.calls.at(index)?.settle(error);
  }

  logout = async (): Promise<void> => {
    this.logouts += 1;
    if (this.logoutFails) throw networkError();
  };
}

/** One simulated browser tab: a minimal store driven by the coordinator. */
class Tab {
  generation = 0;
  token: string | null = null;
  expiresAt: string | null = null;
  user: User | null = USER;
  signedIn = true;
  signOuts: SignOutReason[] = [];
  errors: ApiError[] = [];
  readonly coordinator: RefreshCoordinator;

  constructor(
    server: FakeServer,
    env: { locks?: FakeLocks | null; hub?: FakeBroadcastHub | null },
  ) {
    let attempt = 0;
    const deps: CoordinatorDeps = {
      callRefresh: server.refresh,
      callLogout: server.logout,
      snapshot: () => ({
        generation: this.generation,
        expiresAt: this.expiresAt,
        user: this.user,
        signedIn: this.signedIn,
      }),
      apply: (pair, user, generation) => {
        if (generation !== this.generation) return false;
        this.token = pair.accessToken;
        this.expiresAt = pair.expiresAt;
        if (user) this.user = user;
        this.signedIn = true;
        return true;
      },
      signOut: (reason, generation) => {
        if (generation !== this.generation || !this.signedIn) return;
        this.generation += 1;
        this.signedIn = false;
        this.token = null;
        this.signOuts.push(reason);
      },
      bumpGeneration: () => {
        this.generation += 1;
        return this.generation;
      },
      onError: (error) => this.errors.push(error),
      locks: env.locks ?? null,
      openChannel: env.hub ? (name) => env.hub!.open(name) : null,
      newAttemptId: () => `attempt-${String(++attempt).padStart(14, "0")}-xxxxx`.slice(0, 22),
    };
    this.coordinator = createRefreshCoordinator(deps);
  }
}

async function flush(): Promise<void> {
  for (let i = 0; i < 20; i += 1) await Promise.resolve();
}

describe("refresh coordinator", () => {
  let server: FakeServer;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(T0);
    server = new FakeServer();
  });

  afterEach(() => {
    setUnauthorizedHandler(null);
    setTokenProvider(() => null);
    vi.useRealTimers();
  });

  // ---------------------------------------------------------------- proactive (AC3.10.1)

  it("refreshes once, one minute before the access token expires, and not before", async () => {
    const tab = new Tab(server, {});
    tab.coordinator.schedule(iso(T0 + 15 * 60_000));
    await vi.advanceTimersByTimeAsync(13 * 60_000 + 59_000);
    expect(server.calls).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(1_000);
    expect(server.calls).toHaveLength(1);
    server.succeed();
    await flush();
    expect(tab.token).toBe("token-1");
  });

  it("re-schedules on each new token and cancels with null", async () => {
    const tab = new Tab(server, {});
    tab.coordinator.schedule(iso(T0 + 15 * 60_000));
    tab.coordinator.schedule(iso(T0 + 30 * 60_000));
    await vi.advanceTimersByTimeAsync(15 * 60_000);
    expect(server.calls).toHaveLength(0);
    tab.coordinator.schedule(null);
    await vi.advanceTimersByTimeAsync(30 * 60_000);
    expect(server.calls).toHaveLength(0);
  });

  // ---------------------------------------------------- single flight and 401 retry (AC3.10.2)

  it("shares one refresh between concurrent callers in a tab", async () => {
    const tab = new Tab(server, {});
    const results = Promise.all([1, 2, 3].map(() => tab.coordinator.refresh()));
    await flush();
    expect(server.calls).toHaveLength(1);
    server.succeed();
    const outcomes = await results;
    expect(new Set(outcomes.map((o) => o.accessToken))).toEqual(new Set(["token-1"]));
  });

  it("three concurrent 401s make one refresh call and each request is retried once", async () => {
    const tab = new Tab(server, {});
    configureApiOrigin("http://api.test");
    setTokenProvider(() => tab.token);
    tab.token = "expired";
    setUnauthorizedHandler(() => tab.coordinator.refresh());
    const seen: string[] = [];
    mockFetch((request) => {
      seen.push(`${request.url}|${request.headers.authorization}`);
      return request.headers.authorization === "Bearer expired"
        ? errorResponse(401, "NOT_AUTHENTICATED")
        : jsonResponse(200, { ok: request.url });
    });
    const requests = ["/a", "/b", "/c"].map((path) => apiRequest<{ ok: string }>(path));
    await flush();
    expect(server.calls).toHaveLength(1);
    server.succeed();
    const bodies = await Promise.all(requests);
    expect(bodies.map((b) => b.ok)).toEqual([
      "http://api.test/a",
      "http://api.test/b",
      "http://api.test/c",
    ]);
    expect(seen.filter((s) => s.endsWith("Bearer token-1"))).toHaveLength(3);
    expect(seen).toHaveLength(6);
  });

  // --------------------------------------------------------------- retry limits (AC3.10.3)

  it("does not retry a retried request that gets 401 again", async () => {
    const tab = new Tab(server, {});
    configureApiOrigin("http://api.test");
    setTokenProvider(() => tab.token);
    setUnauthorizedHandler(() => tab.coordinator.refresh());
    const fetched = mockFetch(() => errorResponse(401, "NOT_AUTHENTICATED"));
    const request = apiRequest("/always-401");
    await flush();
    server.succeed();
    await expect(request).rejects.toMatchObject({ code: "NOT_AUTHENTICATED" });
    expect(fetched).toHaveLength(2);
    expect(server.calls).toHaveLength(1);
  });

  it("only NOT_AUTHENTICATED triggers a refresh; other 401 codes are returned as they are", async () => {
    const tab = new Tab(server, {});
    configureApiOrigin("http://api.test");
    setUnauthorizedHandler(() => tab.coordinator.refresh());
    for (const code of [
      "INVALID_CREDENTIALS",
      "CODE_INVALID",
      "RESET_TOKEN_INVALID",
      "SESSION_INVALID",
    ]) {
      mockFetch(() => errorResponse(401, code));
      await expect(apiRequest("/x")).rejects.toMatchObject({ code });
    }
    expect(server.calls).toHaveLength(0);
  });

  it("a refresh that answers 401 starts no further refresh and the request fails", async () => {
    const tab = new Tab(server, {});
    configureApiOrigin("http://api.test");
    setTokenProvider(() => tab.token);
    tab.token = "expired";
    setUnauthorizedHandler(() => tab.coordinator.refresh());
    mockFetch(() => errorResponse(401, "NOT_AUTHENTICATED"));
    const request = apiRequest("/x");
    await flush();
    server.fail(sessionError("REVOKED"));
    await expect(request).rejects.toMatchObject({ code: "SESSION_INVALID" });
    await flush();
    expect(server.calls).toHaveLength(1);
  });

  // ---------------------------------------------------- refresh 401: clear once (AC3.10.4)

  it("a refresh 401 signs out once and rejects every waiter", async () => {
    const tab = new Tab(server, {});
    const waiters = [1, 2, 3, 4, 5].map(() => tab.coordinator.refresh().catch((e: unknown) => e));
    await flush();
    server.fail(sessionError("REUSE_DETECTED"));
    const results = await Promise.all(waiters);
    expect(results.every((r) => r instanceof ApiError && r.code === "SESSION_INVALID")).toBe(true);
    expect(tab.signOuts).toEqual(["security"]);
    expect(tab.signedIn).toBe(false);
  });

  it("maps the server reason to the sign-out reason", () => {
    expect(reasonFor(sessionError("REUSE_DETECTED"))).toBe("security");
    expect(reasonFor(sessionError("REVOKED"))).toBe("security");
    expect(reasonFor(sessionError("EXPIRED"))).toBe("session_expired");
    expect(reasonFor(sessionError("INVALID"))).toBe("session_expired");
    expect(reasonFor(new ApiError({ status: 401, code: "SESSION_INVALID", message: "x" }))).toBe(
      "session_expired",
    );
  });

  // --------------------------------- network errors keep the user signed in (AC3.10.5, R-04)

  it("retries once with the same attempt id after a network error, then recovers", async () => {
    const tab = new Tab(server, {});
    const outcome = tab.coordinator.refresh();
    await flush();
    server.fail(networkError());
    await flush();
    expect(server.calls).toHaveLength(2);
    expect(server.calls[1].attemptId).toBe(server.calls[0].attemptId);
    server.succeed();
    await expect(outcome).resolves.toMatchObject({ accessToken: "token-1" });
    expect(tab.errors).toEqual([]);
    const next = tab.coordinator.refresh();
    await flush();
    expect(server.calls[2].attemptId).not.toBe(server.calls[0].attemptId);
    server.succeed();
    await next;
  });

  it("after a second network error or 5xx the waiters fail, one error is shown, the user stays", async () => {
    const tab = new Tab(server, {});
    const waiters = [tab.coordinator.refresh(), tab.coordinator.refresh()].map((p) =>
      p.catch((e: unknown) => e),
    );
    await flush();
    server.fail(networkError());
    await flush();
    server.fail(serverError());
    const results = await Promise.all(waiters);
    expect(results.every((r) => r instanceof ApiError)).toBe(true);
    expect(tab.errors).toHaveLength(1);
    expect(tab.signedIn).toBe(true);
    expect(tab.signOuts).toEqual([]);
  });

  it("a hung refresh times out after 10 s, is retried once, and always releases the lock", async () => {
    const locks = fakeLocks();
    const tab = new Tab(server, { locks });
    const outcome = tab.coordinator.refresh().catch((e: unknown) => e);
    await flush();
    expect(locks.held()).toEqual(["auth-refresh"]);
    await vi.advanceTimersByTimeAsync(REFRESH_TIMEOUT_MS);
    expect(server.calls).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(REFRESH_TIMEOUT_MS);
    const result = await outcome;
    expect(result).toBeInstanceOf(ApiError);
    expect(locks.held()).toEqual([]);
    expect(tab.errors).toHaveLength(1);
    expect(tab.signedIn).toBe(true);
  });

  // -------------------------------------------------------------- cross-tab (AC3.11.1)

  it("two tabs refreshing together make one network call; the second adopts the result", async () => {
    const locks = fakeLocks();
    const hub = fakeBroadcast();
    const first = new Tab(server, { locks, hub });
    const second = new Tab(server, { locks, hub });
    const a = first.coordinator.refresh();
    const b = second.coordinator.refresh();
    await flush();
    expect(server.calls).toHaveLength(1);
    server.succeed();
    const [ra, rb] = await Promise.all([a, b]);
    expect(ra.adopted).toBe(false);
    expect(rb).toMatchObject({ adopted: true, accessToken: ra.accessToken });
    expect(server.calls).toHaveLength(1);
    expect(second.token).toBe("token-1");
    expect(hub.posted).toContainEqual(
      expect.objectContaining({ type: "refreshed", accessToken: "token-1" }),
    );
  });

  it("a broadcast received more than 5 s ago is not adopted", async () => {
    const locks = fakeLocks();
    const hub = fakeBroadcast();
    const first = new Tab(server, { locks, hub });
    const second = new Tab(server, { locks, hub });
    const a = first.coordinator.refresh();
    await flush();
    server.succeed();
    await a;
    await vi.advanceTimersByTimeAsync(ADOPT_WINDOW_MS + 1);
    const b = second.coordinator.refresh();
    await flush();
    expect(server.calls).toHaveLength(2);
    server.succeed();
    await expect(b).resolves.toMatchObject({ adopted: false, accessToken: "token-2" });
  });

  it("an idle tab applies a newer broadcast at once and ignores an older one", async () => {
    const hub = fakeBroadcast();
    const idle = new Tab(server, { hub });
    idle.token = "mine";
    idle.expiresAt = iso(T0 + 20 * 60_000);
    const sender = hub.open("auth");
    sender.postMessage({
      type: "refreshed",
      accessToken: "older",
      expiresAt: iso(T0 + 10 * 60_000),
      user: USER,
    });
    await flush();
    expect(idle.token).toBe("mine");
    sender.postMessage({
      type: "refreshed",
      accessToken: "newer",
      expiresAt: iso(T0 + 25 * 60_000),
      user: USER,
    });
    await flush();
    expect(idle.token).toBe("newer");
  });

  it("a signedOut broadcast signs this tab out once with the sender's reason", async () => {
    const hub = fakeBroadcast();
    const tab = new Tab(server, { hub });
    const sender = hub.open("auth");
    sender.postMessage({ type: "signedOut", reason: "security" });
    sender.postMessage({ type: "signedOut", reason: "security" });
    await flush();
    expect(tab.signOuts).toEqual(["security"]);
  });

  it("a refresh 401 tells the other tabs to sign out too", async () => {
    const locks = fakeLocks();
    const hub = fakeBroadcast();
    const first = new Tab(server, { locks, hub });
    const second = new Tab(server, { locks, hub });
    const a = first.coordinator.refresh().catch(() => undefined);
    await flush();
    server.fail(sessionError("REVOKED"));
    await a;
    await flush();
    expect(first.signOuts).toEqual(["security"]);
    expect(second.signOuts).toEqual(["security"]);
  });

  // --------------------------------------------------------------- logout (R-02, R-08)

  it("logout waits for the lock, bumps the generation, calls the server and tells other tabs", async () => {
    const locks = fakeLocks();
    const hub = fakeBroadcast();
    const first = new Tab(server, { locks, hub });
    const second = new Tab(server, { locks, hub });
    const inflight = second.coordinator.refresh();
    await flush();
    const before = first.generation;
    const loggingOut = first.coordinator.logout();
    await flush();
    expect(server.logouts).toBe(0); // still waiting for the lock
    server.succeed();
    await inflight;
    await loggingOut;
    expect(server.logouts).toBe(1);
    expect(first.generation).toBeGreaterThan(before);
    await flush();
    expect(second.signOuts).toEqual(["logout"]);
    expect(hub.posted).toContainEqual({ type: "signedOut", reason: "logout" });
  });

  it("logout still tells other tabs when the server call fails", async () => {
    const hub = fakeBroadcast();
    const first = new Tab(server, { hub });
    const second = new Tab(server, { hub });
    server.logoutFails = true;
    await first.coordinator.logout();
    await flush();
    expect(second.signOuts).toEqual(["logout"]);
  });

  it("a late refresh result never revives a tab that was signed out meanwhile", async () => {
    const hub = fakeBroadcast();
    const tab = new Tab(server, { locks: fakeLocks(), hub });
    const outcome = tab.coordinator.refresh().catch((e: unknown) => e);
    await flush();
    hub.open("auth").postMessage({ type: "signedOut", reason: "logout" });
    await flush();
    server.succeed();
    const result = await outcome;
    expect(result).toBeInstanceOf(ApiError);
    expect(tab.signedIn).toBe(false);
    expect(tab.token).toBeNull();
  });

  // ----------------------------------------------------------- fallbacks (NFR5.8, R-08 e)

  it("without Web Locks, a BroadcastChannel claim lets one tab refresh and the other adopt", async () => {
    const hub = fakeBroadcast();
    const first = new Tab(server, { hub });
    const second = new Tab(server, { hub });
    expect(first.coordinator.mode).toBe("broadcast");
    const a = first.coordinator.refresh();
    const b = second.coordinator.refresh();
    await vi.advanceTimersByTimeAsync(200);
    expect(server.calls).toHaveLength(1);
    server.succeed();
    await flush();
    const [ra, rb] = await Promise.all([a, b]);
    expect(ra.accessToken).toBe(rb.accessToken);
    expect(server.calls).toHaveLength(1);
  });

  it("a claim loser that hears nothing within 12 s refreshes by itself", async () => {
    const hub = fakeBroadcast();
    const first = new Tab(server, { hub });
    const second = new Tab(server, { hub });
    const a = first.coordinator.refresh();
    const b = second.coordinator.refresh();
    await vi.advanceTimersByTimeAsync(200);
    expect(server.calls).toHaveLength(1); // only the claim winner called the server
    await vi.advanceTimersByTimeAsync(CLAIM_CAP_MS);
    // No broadcast arrived (the winner's call hung), so the loser called the server itself.
    expect(server.calls.length).toBeGreaterThanOrEqual(2);
    for (let index = 0; index < server.calls.length; index += 1) server.succeed(index);
    const outcomes = await Promise.all([a, b]);
    expect(outcomes.every((outcome) => !outcome.adopted)).toBe(true);
  });

  it("without locks or broadcast, each tab refreshes on its own", async () => {
    const first = new Tab(server, {});
    const second = new Tab(server, {});
    expect(first.coordinator.mode).toBe("none");
    const a = first.coordinator.refresh();
    const b = second.coordinator.refresh();
    await flush();
    expect(server.calls).toHaveLength(2);
    server.succeed(0);
    server.succeed(1);
    await Promise.all([a, b]);
  });

  // ------------------------------------------------------------------ attempt ids (R-04)

  it("attempt ids are 22 random base64url characters", () => {
    const ids = new Set(Array.from({ length: 50 }, () => newAttemptId()));
    expect(ids.size).toBe(50);
    for (const id of ids) expect(id).toMatch(/^[A-Za-z0-9_-]{22}$/);
  });
});

describe("refresh coordinator scheduling limits", () => {
  it("never fires at once for a far-future expiry (setTimeout overflow)", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(T0);
    const server = new FakeServer();
    const tab = new Tab(server, {});
    tab.coordinator.schedule(iso(T0 + 100 * 365 * 24 * 3600_000));
    await vi.advanceTimersByTimeAsync(60_000);
    expect(server.calls).toHaveLength(0);
    tab.coordinator.dispose();
    vi.useRealTimers();
  });
});
