// In-memory auth store (FE-001, FE-002; U1 BR5.1; U2 BR6.1, BR6.5, BR6.8; ClientSession).
//
// Holds the session status, the access token and its expiry, the user profile, why the
// tab was signed out, a generation counter and the pending code step. No `persist`
// middleware and no Web Storage: a reload starts empty and the session is restored from the
// httpOnly refresh cookie (WF-U2-2). The refresh token never reaches JavaScript.
// Only modules under src/lib/auth may import this file (lint-enforced); UI code uses the
// selectors in ./hooks.
import { create } from "zustand";

import { setTokenProvider } from "@/lib/api/client";
import type { components } from "@/lib/api/types.gen";

import type { SignOutReason, TokenPair } from "./refresh-coordinator";

export type User = components["schemas"]["UserResponse"];
export type CodePurpose = "signup" | "login" | "password_reset";
export type SessionStatus = "initializing" | "signedIn" | "signedOut";

export interface PendingVerification {
  email: string;
  maskedEmail: string;
  purpose: CodePurpose;
  expiresAt: string;
  resendAvailableAt: string;
}

export interface AuthState {
  status: SessionStatus;
  accessToken: string | null;
  accessTokenExpiresAt: string | null;
  user: User | null;
  signedOutReason: SignOutReason | null;
  /** Restore could not reach the server (network or 5xx): show Retry, not login. */
  restoreFailed: boolean;
  /** Bumped by every sign-out; a refresh result for an older generation is discarded. */
  generation: number;
  pending: PendingVerification | null;
}

const initialState: AuthState = {
  status: "initializing",
  accessToken: null,
  accessTokenExpiresAt: null,
  user: null,
  signedOutReason: null,
  restoreFailed: false,
  generation: 0,
  pending: null,
};

export const useAuthStore = create<AuthState>()(() => ({ ...initialState }));

/** Store a signed-in session (token, expiry and profile) in memory. */
export function setSession(accessToken: string, expiresAt: string, user: User): void {
  // A new sign-in starts a new generation, so a restore still in flight is discarded.
  useAuthStore.setState((state) => ({
    generation: state.generation + 1,
    status: "signedIn",
    accessToken,
    accessTokenExpiresAt: expiresAt,
    user,
    signedOutReason: null,
    restoreFailed: false,
    pending: null,
  }));
}

/**
 * Store refreshed tokens if `generation` is still current. Without a known profile (a
 * restore before `/auth/me`), the token is kept but the tab stays `initializing`.
 */
export function applyTokens(pair: TokenPair, user: User | null, generation: number): boolean {
  const state = useAuthStore.getState();
  if (generation !== state.generation || state.status === "signedOut") return false;
  const profile = user ?? state.user;
  useAuthStore.setState({
    accessToken: pair.accessToken,
    accessTokenExpiresAt: pair.expiresAt,
    user: profile,
    status: profile ? "signedIn" : state.status,
    restoreFailed: false,
  });
  return true;
}

/** Replace the profile (after "who am I"); completes a restore. */
export function setUser(user: User): void {
  const state = useAuthStore.getState();
  useAuthStore.setState({
    user,
    status: state.accessToken ? "signedIn" : state.status,
    restoreFailed: false,
  });
}

export function setRestoreFailed(failed: boolean): void {
  useAuthStore.setState({ restoreFailed: failed });
}

/** Remember the code step (masked address, purpose, timing). Memory only. */
export function setPending(pending: PendingVerification | null): void {
  useAuthStore.setState({ pending });
}

export function bumpGeneration(): number {
  const generation = useAuthStore.getState().generation + 1;
  useAuthStore.setState({ generation });
  return generation;
}

/**
 * Sign the tab out once for `generation` (BR6.5). Returns whether the tab had been signed
 * in, so the caller can navigate exactly once. A restore that finds no session records a
 * reason only for security sign-outs, so first-time visitors see no notice.
 */
export function signOutOnce(reason: SignOutReason, generation: number): boolean | null {
  const state = useAuthStore.getState();
  if (generation !== state.generation || state.status === "signedOut") return null;
  const wasSignedIn = state.status === "signedIn";
  useAuthStore.setState({
    ...initialState,
    status: "signedOut",
    signedOutReason: wasSignedIn || reason === "security" ? reason : null,
    generation: state.generation + 1,
    // A restore that ends while a sign-up or login code step is open keeps that step.
    pending: wasSignedIn ? null : state.pending,
  });
  return wasSignedIn;
}

export function setSignedOutReason(reason: SignOutReason | null): void {
  useAuthStore.setState({ signedOutReason: reason });
}

/** Test helper: back to the initial state. */
export function resetAuthStore(): void {
  useAuthStore.setState({ ...initialState }, true);
}

setTokenProvider(() => useAuthStore.getState().accessToken);
