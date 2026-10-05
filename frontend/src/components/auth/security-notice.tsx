"use client";

// Why the user was signed out, shown on /login (BR6.7, AC3.6.4; FD post-review R-03, R-07).
// The reason lives in memory only, so a reload or the next sign-in clears it.
import { useAuth, type SignOutReason } from "@/lib/auth";

export function noticeFor(reason: SignOutReason | null): string | null {
  switch (reason) {
    case "security":
      return "You were signed out for your security. Please log in again.";
    case "password_changed":
      return "Your password was changed. Please log in again.";
    case "session_expired":
      return "Your session ended. Please log in again.";
    default:
      return null; // logout, or no sign-out: no notice
  }
}

export function SecurityNotice() {
  const { signedOutReason } = useAuth();
  const message = noticeFor(signedOutReason);
  if (!message) return null;
  return (
    <p
      role="status"
      className="mb-5 rounded-[var(--radius)] border border-card-border bg-[#eef2f5] p-3 text-base text-heading"
      data-testid="security-notice"
    >
      {message}
    </p>
  );
}
