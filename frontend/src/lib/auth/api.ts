// Backend auth endpoints (contract C1). Called only by modules in src/lib/auth, never by UI
// (FE-007). Refresh and logout go through `apiRaw`, which bypasses the client's 401
// handler, so a refresh 401 can never start another refresh (BR6.4).
import { apiRaw, apiRequest } from "@/lib/api/client";
import type { components } from "@/lib/api/types.gen";

import type { CodePurpose } from "./store";

type Schemas = components["schemas"];

export type RegisterRequest = Schemas["RegisterRequest"];
export type LoginRequest = Schemas["LoginRequest"];
export type VerifyRequest = Schemas["VerifyRequest"];
export type CodeSent = Schemas["CodeSentResponse"];
export type SessionResponse = Schemas["SessionResponse"];
export type UserResponse = Schemas["UserResponse"];
export type AccessTokenResponse = Schemas["AccessTokenResponse"];
export type ResetTokenResponse = Schemas["ResetTokenResponse"];

export function postRegister(body: RegisterRequest): Promise<CodeSent> {
  return apiRequest<CodeSent>("/auth/register", { method: "POST", body });
}

export function postLogin(body: LoginRequest): Promise<CodeSent> {
  return apiRequest<CodeSent>("/auth/login", { method: "POST", body });
}

export function postVerify(body: VerifyRequest): Promise<SessionResponse> {
  return apiRequest<SessionResponse>("/auth/verify", { method: "POST", body });
}

export function getMe(): Promise<UserResponse> {
  return apiRequest<UserResponse>("/auth/me");
}

// --- U2 -------------------------------------------------------------------------------

/** POST /auth/refresh with the per-call attempt id (FD post-review R-04). */
export function postRefresh(attemptId: string, signal: AbortSignal): Promise<AccessTokenResponse> {
  return apiRaw<AccessTokenResponse>("/auth/refresh", {
    method: "POST",
    headers: { "X-Refresh-Attempt": attemptId },
    signal,
  });
}

export function postLogout(): Promise<void> {
  return apiRaw<void>("/auth/logout", { method: "POST" });
}

export function postResendCode(email: string, purpose: CodePurpose): Promise<CodeSent> {
  return apiRequest<CodeSent>("/auth/resend-code", { method: "POST", body: { email, purpose } });
}

export function postForgotPassword(email: string): Promise<CodeSent> {
  return apiRequest<CodeSent>("/auth/password/forgot", { method: "POST", body: { email } });
}

export function postVerifyResetCode(email: string, code: string): Promise<ResetTokenResponse> {
  return apiRequest<ResetTokenResponse>("/auth/password/verify-code", {
    method: "POST",
    body: { email, code },
  });
}

export function postResetPassword(resetToken: string, newPassword: string): Promise<void> {
  return apiRequest<void>("/auth/password/reset", {
    method: "POST",
    body: { resetToken, newPassword },
  });
}

export function postChangePassword(currentPassword: string, newPassword: string): Promise<void> {
  return apiRequest<void>("/auth/change-password", {
    method: "POST",
    body: { currentPassword, newPassword },
  });
}
