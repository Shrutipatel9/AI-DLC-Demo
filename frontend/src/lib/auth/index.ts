// The only auth entry point for UI code (Section 5.3): selectors and commands.
export { useAuth, useAuthActions, type AuthView } from "./hooks";
export type { SignOutReason } from "./refresh-coordinator";
export type { SessionNotifier } from "./session";
export type { User, CodePurpose, SessionStatus } from "./store";
