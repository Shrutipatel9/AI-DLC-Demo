// Public selectors and actions for UI code (FE-007, BR5.3, AC1.9.3). UI never sees the
// access token or the reset token: these hooks expose the profile, flags and commands only.
import { useMemo } from "react";

import * as actions from "./actions";
import type { SignOutReason } from "./refresh-coordinator";
import { setSessionNotifier } from "./session";
import { useAuthStore, type PendingVerification, type SessionStatus, type User } from "./store";

export interface AuthView {
  user: User | null;
  status: SessionStatus;
  isAuthenticated: boolean;
  initializing: boolean;
  restoreFailed: boolean;
  signedOutReason: SignOutReason | null;
  pending: Omit<PendingVerification, "email"> | null;
  pendingEmail: string | null;
}

/** Read-only auth state for components. Each selector returns a stable value. */
export function useAuth(): AuthView {
  const user = useAuthStore((state) => state.user);
  const status = useAuthStore((state) => state.status);
  const restoreFailed = useAuthStore((state) => state.restoreFailed);
  const signedOutReason = useAuthStore((state) => state.signedOutReason);
  const pending = useAuthStore((state) => state.pending);
  return useMemo(() => {
    const view: AuthView = {
      user,
      status,
      isAuthenticated: status === "signedIn",
      initializing: status === "initializing",
      restoreFailed,
      signedOutReason,
      pending: null,
      pendingEmail: pending?.email ?? null,
    };
    if (pending) {
      view.pending = {
        maskedEmail: pending.maskedEmail,
        purpose: pending.purpose,
        expiresAt: pending.expiresAt,
        resendAvailableAt: pending.resendAvailableAt,
      };
    }
    return view;
  }, [user, status, restoreFailed, signedOutReason, pending]);
}

const commands = {
  signUp: actions.signUp,
  logIn: actions.logIn,
  verifyCode: actions.verifyCode,
  resendCode: actions.resendCode,
  loadCurrentUser: actions.loadCurrentUser,
  restore: actions.restore,
  logout: actions.logout,
  requestPasswordReset: actions.requestPasswordReset,
  verifyResetCode: actions.verifyResetCode,
  hasResetToken: actions.hasResetToken,
  resetPassword: actions.resetPassword,
  changePassword: actions.changePassword,
  cancelPending: actions.cancelPending,
  setSessionNotifier,
} as const;

/** Auth commands for components (a stable object). */
export function useAuthActions(): typeof commands {
  return commands;
}
