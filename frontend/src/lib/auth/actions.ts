// Auth actions: the store's commands. They call the auth API through the single client and
// update the in-memory store (layering: UI -> store/actions -> API client -> backend).
import { ApiError, isApiError } from "@/lib/api/errors";

import {
  getMe,
  postChangePassword,
  postForgotPassword,
  postLogin,
  postRegister,
  postResendCode,
  postResetPassword,
  postVerify,
  postVerifyResetCode,
} from "./api";
import { getCoordinator, logout, restore, startSession } from "./session";
import {
  setPending,
  setSignedOutReason,
  setUser,
  useAuthStore,
  type CodePurpose,
  type User,
} from "./store";

export interface SignUpInput {
  fullName: string;
  email: string;
  password: string;
}

export interface LogInInput {
  email: string;
  password: string;
}

/**
 * The reset token from a verified reset code, held in memory only and never exposed to UI
 * code (FE-007; WF-U2-7 step 3: "kept in page memory"). A reload forgets it.
 */
let resetToken: string | null = null;

function normalise(email: string): string {
  return email.trim().toLowerCase();
}

function requirePending(): NonNullable<ReturnType<typeof useAuthStore.getState>["pending"]> {
  const pending = useAuthStore.getState().pending;
  if (!pending) {
    throw new Error("No code step in progress");
  }
  return pending;
}

/** Step 1 of sign-up: the server emails a code. Remembers the code step in memory. */
export async function signUp(input: SignUpInput): Promise<void> {
  const sent = await postRegister(input);
  setPending({ email: normalise(input.email), purpose: "signup", ...sent });
}

/** Step 1 of login: the server checks the password and emails a code. */
export async function logIn(input: LogInInput): Promise<void> {
  const sent = await postLogin(input);
  setPending({ email: normalise(input.email), purpose: "login", ...sent });
}

/** Step 2: verify the emailed code; on success the session lives in memory only. */
export async function verifyCode(code: string): Promise<User> {
  const pending = requirePending();
  if (pending.purpose === "password_reset") {
    throw new Error("Use verifyResetCode for a reset code");
  }
  const session = await postVerify({ email: pending.email, code, purpose: pending.purpose });
  startSession(session.accessToken, session.expiresAt, session.user);
  return session.user;
}

/** WF-U2-1: ask for a new code for the current step; restarts the countdown. */
export async function resendCode(): Promise<void> {
  const pending = requirePending();
  const sent = await postResendCode(pending.email, pending.purpose);
  setPending({ ...pending, ...sent });
}

/** WF-U2-7 step 1: request a reset code. The answer never says whether the email exists. */
export async function requestPasswordReset(email: string): Promise<void> {
  const sent = await postForgotPassword(email);
  resetToken = null;
  setPending({ email: normalise(email), purpose: "password_reset", ...sent });
}

/** WF-U2-7 step 2: verify the reset code; the reset token stays in memory here. */
export async function verifyResetCode(code: string): Promise<void> {
  const pending = requirePending();
  const issued = await postVerifyResetCode(pending.email, code);
  resetToken = issued.resetToken;
  setPending(null);
}

/** Whether step 3 can run (a reload forgets the token, and the page offers to start again). */
export function hasResetToken(): boolean {
  return resetToken !== null;
}

/** WF-U2-7 step 3: set the new password; every session of the account ends. */
export async function resetPassword(newPassword: string): Promise<void> {
  if (!resetToken) {
    throw new ApiError({
      status: 401,
      code: "RESET_TOKEN_INVALID",
      message: "This reset link has expired. Please start again.",
    });
  }
  await postResetPassword(resetToken, newPassword);
  resetToken = null;
}

/**
 * WF-U2-8: change the password. This tab's session is kept by the server; the tab then
 * refreshes once. If that refresh is refused, the tab is signed out with the
 * "password changed" notice (FD post-review R-03), so the user is never dropped silently.
 */
export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await postChangePassword(currentPassword, newPassword);
  try {
    await getCoordinator().refresh();
  } catch (error) {
    if (isApiError(error) && error.status === 401) {
      setSignedOutReason("password_changed");
      throw new ApiError({
        status: 401,
        code: "SESSION_INVALID",
        message: "Your password was changed. Please log in again.",
      });
    }
    // A network error after a successful change: the password is changed; the next
    // request will refresh again.
  }
}

/** "Who am I" (AC3.8.1). Returns null when the session has ended. */
export async function loadCurrentUser(): Promise<User | null> {
  if (!useAuthStore.getState().accessToken) {
    return null;
  }
  try {
    const user = await getMe();
    setUser(user);
    return user;
  } catch (error) {
    if (isApiError(error) && error.status === 401) {
      return null;
    }
    throw error;
  }
}

/** Forget the code step (for "Wrong email? Go back"). */
export function cancelPending(): void {
  setPending(null);
}

export { logout, restore };
export type { CodePurpose, User };
