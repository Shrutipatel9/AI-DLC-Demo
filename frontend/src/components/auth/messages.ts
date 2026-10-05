// Plain-language messages for API error codes (the UI branches on `code` only).
import type { ApiError } from "@/lib/api/errors";

export const GENERIC_ERROR = "Something went wrong on our side. Please try again.";

/** Format a "try again at HH:MM" time from a Retry-After value. */
export function retryClock(seconds: number | null, now: Date = new Date()): string {
  const at = new Date(now.getTime() + (seconds ?? 0) * 1000);
  return at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** A user-facing message for an API error. */
export function messageFor(error: ApiError): string {
  switch (error.code) {
    case "INVALID_CREDENTIALS":
      return "Email or password is incorrect.";
    case "EMAIL_ALREADY_REGISTERED":
      return "An account with this email already exists. Sign in instead?";
    case "CODE_RESEND_COOLDOWN":
      return `Please wait ${error.retryAfterSeconds ?? 60} seconds before asking for a new code.`;
    case "CODE_LOCKED":
      return `Too many tries. You can try again at ${retryClock(error.retryAfterSeconds)}.`;
    case "CODE_EXPIRED":
      return "This code has expired.";
    case "CODE_INVALID": {
      const left = error.attemptsLeft;
      return left === null
        ? "That code isn't right."
        : `That code isn't right. ${left} ${left === 1 ? "try" : "tries"} left.`;
    }
    case "RATE_LIMITED":
      return "Too many attempts. Please wait a minute and try again.";
    case "UPSTREAM_UNAVAILABLE":
    case "UPSTREAM_TIMEOUT":
      return "We couldn't send the email. Please try again.";
    case "NETWORK_ERROR":
      return "We couldn't reach the server. Check your connection and try again.";
    case "TIMEOUT":
      return "The server took too long to answer. Please try again.";
    case "VALIDATION_FAILED":
      return "Please check the highlighted fields.";
    default:
      return GENERIC_ERROR;
  }
}

/** Field-level message for a VALIDATION_FAILED reason from the server. */
export function fieldMessage(field: string, reason: string): string {
  if (field === "password" && reason === "PASSWORD_TOO_WEAK") {
    return "This password is too common or too weak — try another.";
  }
  if (field === "email") return "Enter a valid email address.";
  if (field === "fullName") return "Enter your full name (up to 120 characters).";
  if (field === "code") return "Enter the 6-digit code.";
  return "Please check this field.";
}
