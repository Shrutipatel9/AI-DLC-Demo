// Session wiring: the one refresh coordinator per tab, connected to the store, the auth API
// and the browser's Web Locks and BroadcastChannel (WF-U2-2 to WF-U2-6). Private to
// src/lib/auth. UI reaches it only through the commands in ./hooks.
import { setUnauthorizedHandler } from "@/lib/api/client";
import { ApiError, isApiError } from "@/lib/api/errors";

import { getMe, postLogout, postRefresh } from "./api";
import {
  createRefreshCoordinator,
  type ChannelLike,
  type LockManagerLike,
  type RefreshCoordinator,
  type SignOutReason,
} from "./refresh-coordinator";
import {
  applyTokens,
  bumpGeneration,
  setRestoreFailed,
  setSession,
  setUser,
  signOutOnce,
  useAuthStore,
  type User,
} from "./store";

/** UI services the session needs but must not import (layering): toasts and navigation. */
export interface SessionNotifier {
  error(message: string): void;
  navigate(path: string): void;
}

export interface SessionEnvironment {
  locks: LockManagerLike | null;
  openChannel: ((name: string) => ChannelLike) | null;
}

let notifier: SessionNotifier = { error: () => undefined, navigate: () => undefined };
let environment: SessionEnvironment | null = null;
let coordinator: RefreshCoordinator | null = null;
let restoring: Promise<void> | null = null;

function browserEnvironment(): SessionEnvironment {
  const nav = typeof navigator === "undefined" ? undefined : navigator;
  const locks = (nav as { locks?: LockManagerLike } | undefined)?.locks ?? null;
  const Channel = typeof window === "undefined" ? undefined : window.BroadcastChannel;
  return { locks, openChannel: Channel ? (name) => new Channel(name) : null };
}

/** Register the toast and router used by the session (AuthBootstrap does this once). */
export function setSessionNotifier(next: SessionNotifier): void {
  notifier = next;
}

/** Tests: choose the lock and channel implementations, and start from a fresh coordinator. */
export function resetSession(next: SessionEnvironment | null = null): void {
  coordinator?.dispose();
  coordinator = null;
  setUnauthorizedHandler(null);
  restoring = null;
  environment = next;
}

function signOut(reason: SignOutReason, generation: number): void {
  if (signOutOnce(reason, generation)) notifier.navigate("/login");
}

export function getCoordinator(): RefreshCoordinator {
  if (coordinator) return coordinator;
  const env = environment ?? browserEnvironment();
  coordinator = createRefreshCoordinator({
    callRefresh: postRefresh,
    callLogout: postLogout,
    snapshot: () => {
      const state = useAuthStore.getState();
      return {
        generation: state.generation,
        expiresAt: state.accessTokenExpiresAt,
        user: state.user,
        signedIn: state.status === "signedIn",
      };
    },
    apply: applyTokens,
    signOut,
    bumpGeneration,
    onError: (error) => {
      // During restore the full-page loader shows its own Retry message instead.
      if (useAuthStore.getState().status === "signedIn") notifier.error(error.message);
    },
    locks: env.locks,
    openChannel: env.openChannel,
  });
  setUnauthorizedHandler(async () => {
    if (useAuthStore.getState().status === "signedOut") {
      throw new ApiError({ status: 401, code: "SESSION_INVALID", message: "You are signed out." });
    }
    await getCoordinator().refresh();
  });
  return coordinator;
}

/** A sign-in finished (code verified): keep it in memory and schedule the renewal. */
export function startSession(accessToken: string, expiresAt: string, user: User): void {
  setSession(accessToken, expiresAt, user);
  getCoordinator().schedule(expiresAt);
}

async function runRestore(): Promise<void> {
  setRestoreFailed(false);
  try {
    const outcome = await getCoordinator().refresh();
    if (!outcome.user) setUser(await getMe());
  } catch (error) {
    // 401: the coordinator already signed the tab out. Anything else: offer Retry.
    if (isApiError(error) && error.status === 401) return;
    setRestoreFailed(true);
  }
}

/** WF-U2-2: restore the session from the refresh cookie (once per call; shared). */
export function restore(): Promise<void> {
  restoring ??= runRestore().finally(() => {
    restoring = null;
  });
  return restoring;
}

/** WF-U2-6: revoke on the server (under the lock), tell other tabs, clear this tab. */
export async function logout(): Promise<void> {
  await getCoordinator().logout();
  const { generation } = useAuthStore.getState();
  signOutOnce("logout", generation);
}
