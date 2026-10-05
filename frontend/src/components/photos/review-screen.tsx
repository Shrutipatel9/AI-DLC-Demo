"use client";

// The review screen for the same-person check (US5.11; FR-006, [IV] §1, §6). It renders only the
// CURRENT server result: a flagged photo is highlighted with text and an icon (not colour
// alone), Continue stays disabled with its reason while anything is flagged or pending, and
// nothing ever navigates on its own: only a click on Continue moves on (AC5.11.1-AC5.11.5).
import { CircleCheck, TriangleAlert } from "lucide-react";
import { useId } from "react";

import { Button } from "@/components/ui/button";
import {
  continueState,
  entryFor,
  flaggedAngles,
  progressText,
  type AngleInfo,
  type IdentityResult,
  type PhotoSet,
} from "@/lib/photos";
import { cn } from "@/lib/utils";

import { CONTINUE_REASON, MISMATCH_MESSAGE } from "./messages";
import { PhotoThumbnail } from "./photo-thumbnail";

export function ReviewScreen({
  photoSet,
  identity,
  angles,
  onRetake,
  onContinue,
}: {
  photoSet: PhotoSet;
  /** null while a fresh result is pending (never treated as consistent). */
  identity: IdentityResult | null;
  angles: AngleInfo[];
  onRetake: (angle: string) => void;
  onContinue: () => void;
}) {
  const reasonId = useId();
  const flagged = flaggedAngles(identity);
  const state = continueState(photoSet, identity);
  const label = (id: string) => angles.find((angle) => angle.id === id)?.label ?? id;

  return (
    <section className="space-y-5" data-testid="photo-review">
      <div>
        <h1 className="text-2xl font-bold text-heading">Review your photos</h1>
        <p className="mt-2 text-base text-muted" data-testid="review-status" aria-live="polite">
          {identity === null
            ? "Checking your photos…"
            : flagged.length > 0
              ? "One or more photos need a retake."
              : state.enabled
                ? `All ${photoSet.requiredAngles.length} photos look good.`
                : `${progressText(photoSet)} photos done. Add a photo for every angle.`}
        </p>
      </div>
      <ul className="grid grid-cols-3 gap-2 sm:gap-4">
        {photoSet.requiredAngles.map((angle) => {
          const entry = entryFor(photoSet, angle);
          const isFlagged = flagged.includes(angle);
          return (
            <li
              key={angle}
              className={cn(
                "flex min-w-0 flex-col gap-2 rounded-[var(--radius)] border p-2",
                isFlagged ? "border-2 border-danger bg-white" : "border-card-border",
              )}
              data-testid={`review-photo-${angle}`}
              data-flagged={isFlagged ? "true" : "false"}
            >
              <p className="truncate text-sm font-semibold text-heading">{label(angle)}</p>
              {entry.imageUrl ? (
                <PhotoThumbnail imageUrl={entry.imageUrl} alt={`Your ${label(angle)} photo`} />
              ) : (
                <div className="flex aspect-[4/5] items-center justify-center rounded-[var(--radius)] border border-dashed border-card-border text-sm text-muted">
                  No photo
                </div>
              )}
              {isFlagged ? (
                <p
                  className="flex items-start gap-1 text-xs text-heading sm:text-sm"
                  data-testid={`review-flag-${angle}`}
                >
                  <TriangleAlert
                    className="mt-0.5 h-4 w-4 shrink-0 text-danger"
                    aria-hidden="true"
                  />
                  <span>
                    <span className="sr-only">Needs a retake: </span>
                    {MISMATCH_MESSAGE}
                  </span>
                </p>
              ) : entry.status === "accepted" && identity?.status === "consistent" ? (
                <p className="flex items-center gap-1 text-xs text-heading sm:text-sm">
                  <CircleCheck className="h-4 w-4 shrink-0 text-success" aria-hidden="true" />
                  Looks good
                </p>
              ) : null}
              <Button
                variant={isFlagged ? "primary" : "secondary"}
                className="min-h-10 px-2 text-sm"
                onClick={() => onRetake(angle)}
                data-testid={`review-retake-${angle}`}
                aria-label={`Retake the ${label(angle)} photo`}
              >
                Retake
              </Button>
            </li>
          );
        })}
      </ul>
      <div className="flex flex-wrap items-center gap-3">
        <Button
          onClick={onContinue}
          disabled={!state.enabled}
          aria-describedby={state.enabled ? undefined : reasonId}
          data-testid="review-continue-button"
        >
          Continue
        </Button>
        {state.enabled ? null : (
          <p id={reasonId} className="text-sm text-heading" data-testid="review-continue-reason">
            {CONTINUE_REASON[state.reason]}
          </p>
        )}
      </div>
    </section>
  );
}
