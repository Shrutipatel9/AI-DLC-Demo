// Pure helpers over the server's photo set. The server's PhotoSet is the only truth: these
// derive what the screens show and never remember an earlier same-person result ([IV] §1).
import type { IdentityResult, PhotoEntry, PhotoSet } from "./api";

/** The angle's entry in the set (a missing entry reads as `missing`). */
export function entryFor(set: PhotoSet, angle: string): PhotoEntry {
  return (
    set.photos.find((photo) => photo.angle === angle) ?? {
      angle,
      status: "missing",
      reasons: [],
      imageUrl: null,
    }
  );
}

/** "2 of 3": accepted photos counted against the configured angles (AC5.2.6). */
export function progressText(set: PhotoSet): string {
  return `${set.acceptedCount} of ${set.requiredAngles.length}`;
}

/**
 * The next configured angle without an accepted photo, looking after `after` first and then
 * from the start; null when every angle is accepted.
 */
export function nextAngle(set: PhotoSet, after?: string): string | null {
  const angles = set.requiredAngles;
  const start = after ? angles.indexOf(after) + 1 : 0;
  const ordered = [...angles.slice(start), ...angles.slice(0, start)];
  return ordered.find((angle) => entryFor(set, angle).status !== "accepted") ?? null;
}

export function isComplete(set: PhotoSet): boolean {
  return nextAngle(set) === null;
}

/** Angles the same-person check flagged; empty unless the result is `mismatch`. */
export function flaggedAngles(identity: IdentityResult | null): string[] {
  return identity?.status === "mismatch" ? identity.mismatchedAngles : [];
}

export type ContinueState =
  { enabled: true } | { enabled: false; reason: "pending" | "mismatch" | "incomplete" };

/**
 * Whether Continue is enabled on the review screen. `identity === null` means a fresh result
 * is still pending, which is NOT consistent ([IV] §6; AC5.11.3).
 */
export function continueState(set: PhotoSet, identity: IdentityResult | null): ContinueState {
  if (identity === null) return { enabled: false, reason: "pending" };
  if (!isComplete(set) || identity.status === "incomplete") {
    return { enabled: false, reason: "incomplete" };
  }
  if (identity.status === "mismatch") return { enabled: false, reason: "mismatch" };
  return { enabled: true };
}
