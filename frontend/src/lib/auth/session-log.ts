// Development-only session diagnostics (NFR5.11). Records the refresh failure class, the
// sign-out reason and the cross-tab lock mode. It never receives tokens, ids or emails,
// and production builds are silent.
export type SessionLogEvent = "refresh-failed" | "signed-out" | "lock-mode" | "logout-failed";

export function sessionLog(event: SessionLogEvent, detail: string): void {
  if (process.env.NODE_ENV !== "development") return;
  console.info(`[session] ${event}: ${detail}`);
}
