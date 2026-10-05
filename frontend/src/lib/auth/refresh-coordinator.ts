// Refresh coordinator (FE-005, FE-006, ADR-006; WF-U2-3, WF-U2-4).
//
// Private to src/lib/auth: the store wires it, UI code never sees it (FE-007).
//
// - Single flight per tab: every caller (start-up, proactive timer, 401 handler) awaits one
//   shared promise.
// - Single flight across tabs: the exclusive Web Lock "auth-refresh". With the lock held, a
//   `refreshed` broadcast received under 5 s ago is adopted instead of calling the server;
//   otherwise this tab calls /auth/refresh and broadcasts the result on the "auth" channel.
// - Fallback without Web Locks: a BroadcastChannel claim (the smallest (time, id) wins; a
//   loser waits up to 12 s for the winner's broadcast). Without both: per-tab refresh.
// - Each refresh has a random attempt id (16 bytes, base64url) kept only in this closure.
//   A network error, 5xx or the 10 s timeout releases the lock, re-takes it and retries once
//   with the same id, so a lost response is recovered by the server (FD post-review R-04).
// - A refresh 401 signs out exactly once, tells the other tabs, and rejects every waiter.
//   Any other failure keeps the user signed in and reports one error.
// - A store generation is captured at the start of each refresh; a result for an older
//   generation (the user logged out meanwhile) is discarded, never applied.
import { ApiError, isApiError } from "@/lib/api/errors";

import { sessionLog } from "./session-log";
import type { User } from "./store";

export interface TokenPair {
  accessToken: string;
  expiresAt: string;
}

/** Why a tab was signed out; drives the notice on the login screen. */
export type SignOutReason = "logout" | "session_expired" | "security" | "password_changed";

export interface RefreshOutcome extends TokenPair {
  /** The profile carried by an adopted broadcast or held by this tab (may be null). */
  user: User | null;
  /** True when another tab's result was used and no network call was made. */
  adopted: boolean;
}

export interface LockManagerLike {
  request<T>(name: string, options: { mode: "exclusive" }, callback: () => Promise<T>): Promise<T>;
}

export interface ChannelLike {
  postMessage(message: unknown): void;
  addEventListener(type: "message", listener: (event: MessageEvent) => void): void;
  close(): void;
}

export interface CoordinatorSnapshot {
  generation: number;
  expiresAt: string | null;
  user: User | null;
  signedIn: boolean;
}

export interface CoordinatorDeps {
  /** POST /auth/refresh outside the 401 handler; must reject with ApiError. */
  callRefresh(attemptId: string, signal: AbortSignal): Promise<TokenPair>;
  /** POST /auth/logout. */
  callLogout(): Promise<void>;
  snapshot(): CoordinatorSnapshot;
  /** Store the token if `generation` is still current; false means "discarded". */
  apply(pair: TokenPair, user: User | null, generation: number): boolean;
  /** Clear the store once for this generation. */
  signOut(reason: SignOutReason, generation: number): void;
  bumpGeneration(): number;
  /** Report a refresh failure that keeps the user signed in (one error toast). */
  onError(error: ApiError): void;
  locks?: LockManagerLike | null;
  openChannel?: ((name: string) => ChannelLike) | null;
  newAttemptId?: () => string;
}

export interface RefreshCoordinator {
  readonly mode: "locks" | "broadcast" | "none";
  refresh(): Promise<RefreshOutcome>;
  schedule(expiresAt: string | null): void;
  logout(): Promise<void>;
  dispose(): void;
}

export const LOCK_NAME = "auth-refresh";
export const CHANNEL_NAME = "auth";
export const REFRESH_TIMEOUT_MS = 10_000;
export const ADOPT_WINDOW_MS = 5_000;
export const PROACTIVE_LEAD_MS = 60_000;
export const CLAIM_WAIT_MS = 150;
export const CLAIM_CAP_MS = 12_000;
const MAX_TIMER_MS = 2_147_483_647;

type Message =
  | { type: "refreshed"; accessToken: string; expiresAt: string; user: User | null }
  | { type: "signedOut"; reason: SignOutReason }
  | { type: "claim"; id: string; at: number };

interface Received {
  pair: TokenPair;
  user: User | null;
  receivedAt: number;
}

interface Claim {
  id: string;
  at: number;
  receivedAt: number;
}

/** 16 random bytes as 22 base64url characters (the X-Refresh-Attempt header). */
export function newAttemptId(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Server reason -> sign-out reason (FD post-review R-07). */
export function reasonFor(error: ApiError): SignOutReason {
  const reason = error.details[0]?.reason;
  return reason === "REUSE_DETECTED" || reason === "REVOKED" ? "security" : "session_expired";
}

function signedOutError(): ApiError {
  return new ApiError({ status: 401, code: "SESSION_INVALID", message: "You are signed out." });
}

function isRetryable(error: unknown): boolean {
  return isApiError(error) && (error.status === 0 || error.status >= 500);
}

function isMessage(data: unknown): data is Message {
  return typeof data === "object" && data !== null && "type" in data;
}

function isNewer(candidate: string, current: string | null): boolean {
  return current === null || Date.parse(candidate) > Date.parse(current);
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function createRefreshCoordinator(deps: CoordinatorDeps): RefreshCoordinator {
  const locks = deps.locks ?? null;
  const channel = deps.openChannel ? deps.openChannel(CHANNEL_NAME) : null;
  const mode: RefreshCoordinator["mode"] = locks ? "locks" : channel ? "broadcast" : "none";
  const makeAttemptId = deps.newAttemptId ?? newAttemptId;
  let inflight: Promise<RefreshOutcome> | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let lastBroadcast: Received | null = null;
  const claims: Claim[] = [];
  const broadcastWaiters = new Set<() => void>();
  sessionLog("lock-mode", mode);

  function post(message: Message): void {
    channel?.postMessage(message);
  }

  function cancel(): void {
    if (timer !== null) clearTimeout(timer);
    timer = null;
  }

  function schedule(expiresAt: string | null): void {
    cancel();
    if (!expiresAt) return;
    // setTimeout fires at once for delays above 2^31 - 1 ms, so clamp far-future expiries.
    const wait = Math.min(
      MAX_TIMER_MS,
      Math.max(0, Date.parse(expiresAt) - PROACTIVE_LEAD_MS - Date.now()),
    );
    timer = setTimeout(() => {
      timer = null;
      // A failure was already reported through onError (or signed the tab out).
      refresh().catch(() => undefined);
    }, wait);
  }

  function onMessage(data: unknown): void {
    if (!isMessage(data)) return;
    if (data.type === "claim") {
      claims.push({ id: data.id, at: data.at, receivedAt: Date.now() });
      return;
    }
    if (data.type === "signedOut") {
      cancel();
      deps.signOut(data.reason, deps.snapshot().generation);
    } else {
      const pair = { accessToken: data.accessToken, expiresAt: data.expiresAt };
      lastBroadcast = { pair, user: data.user, receivedAt: Date.now() };
      const current = deps.snapshot();
      if (current.signedIn && isNewer(pair.expiresAt, current.expiresAt)) {
        if (deps.apply(pair, data.user, current.generation)) schedule(pair.expiresAt);
      }
    }
    for (const wake of broadcastWaiters) wake();
  }

  channel?.addEventListener("message", (event) => onMessage(event.data));

  function waitForBroadcast(ms: number): Promise<void> {
    return new Promise((resolve) => {
      const done = () => {
        clearTimeout(cap);
        broadcastWaiters.delete(done);
        resolve();
      };
      const cap = setTimeout(done, ms);
      broadcastWaiters.add(done);
    });
  }

  /** BroadcastChannel claim-and-wait (no Web Locks): the smallest (time, id) refreshes. */
  async function claimThenRun<T>(work: () => Promise<T>): Promise<T> {
    const mine = { id: newAttemptId(), at: Date.now() };
    post({ type: "claim", ...mine });
    await delay(CLAIM_WAIT_MS);
    const rival = claims.some(
      (claim) =>
        Date.now() - claim.receivedAt <= 2 * CLAIM_WAIT_MS &&
        (claim.at < mine.at || (claim.at === mine.at && claim.id < mine.id)),
    );
    if (rival) await waitForBroadcast(CLAIM_CAP_MS);
    return work();
  }

  function exclusive<T>(work: () => Promise<T>): Promise<T> {
    if (locks) return locks.request(LOCK_NAME, { mode: "exclusive" }, work);
    if (channel) return claimThenRun(work);
    return work();
  }

  function withTimeout(attemptId: string): Promise<TokenPair> {
    const controller = new AbortController();
    let expiry: ReturnType<typeof setTimeout> | undefined;
    const timeout = new Promise<never>((_, reject) => {
      expiry = setTimeout(() => {
        controller.abort();
        reject(new ApiError({ status: 0, code: "TIMEOUT", message: "The refresh timed out." }));
      }, REFRESH_TIMEOUT_MS);
    });
    return Promise.race([deps.callRefresh(attemptId, controller.signal), timeout]).finally(() =>
      clearTimeout(expiry),
    );
  }

  /** One locked attempt: adopt a fresh broadcast, or call the server and broadcast. */
  async function attempt(attemptId: string, generation: number): Promise<RefreshOutcome> {
    const recent =
      lastBroadcast && Date.now() - lastBroadcast.receivedAt < ADOPT_WINDOW_MS
        ? lastBroadcast
        : null;
    if (recent) {
      if (!deps.apply(recent.pair, recent.user, generation)) throw signedOutError();
      schedule(recent.pair.expiresAt);
      return { ...recent.pair, user: recent.user, adopted: true };
    }
    let pair: TokenPair;
    try {
      pair = await withTimeout(attemptId);
    } catch (error) {
      if (isApiError(error) && error.status === 401) {
        const reason = reasonFor(error);
        cancel();
        deps.signOut(reason, generation);
        post({ type: "signedOut", reason });
        sessionLog("signed-out", reason);
      }
      throw error;
    }
    const user = deps.snapshot().user;
    if (!deps.apply(pair, user, generation)) throw signedOutError();
    post({ type: "refreshed", ...pair, user });
    schedule(pair.expiresAt);
    return { ...pair, user, adopted: false };
  }

  async function run(): Promise<RefreshOutcome> {
    const generation = deps.snapshot().generation;
    const attemptId = makeAttemptId();
    try {
      return await exclusive(() => attempt(attemptId, generation));
    } catch (error) {
      if (!isRetryable(error)) throw report(error);
      sessionLog("refresh-failed", (error as ApiError).code);
    }
    // The lock was released; take it again and retry once with the same attempt id.
    try {
      return await exclusive(() => attempt(attemptId, generation));
    } catch (error) {
      throw report(error);
    }
  }

  function report(error: unknown): unknown {
    if (isApiError(error) && error.status !== 401) {
      sessionLog("refresh-failed", error.code);
      deps.onError(error);
    }
    return error;
  }

  function refresh(): Promise<RefreshOutcome> {
    inflight ??= run().finally(() => {
      inflight = null;
    });
    return inflight;
  }

  async function logout(): Promise<void> {
    cancel();
    const work = async () => {
      deps.bumpGeneration();
      try {
        await deps.callLogout();
      } catch (error) {
        // WF-U2-6 step 4: the tab signs out whatever the server says.
        sessionLog("logout-failed", isApiError(error) ? error.code : "unknown");
      }
      post({ type: "signedOut", reason: "logout" });
    };
    await (locks ? locks.request(LOCK_NAME, { mode: "exclusive" }, work) : work());
  }

  return {
    mode,
    refresh,
    schedule,
    logout,
    dispose() {
      cancel();
      channel?.close();
    },
  };
}
