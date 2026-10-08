// Plain-language text for the analysis screens. The UI branches on error codes only.
import { messageFor } from "@/components/auth/messages";
import type { ApiError } from "@/lib/api/errors";
import type { AnalysisStepKey, AnalysisStepState } from "@/lib/analysis";

export const ANALYSIS_STEP_LABEL = "Step 5 of 5 · Analysis";

const STEP_LABELS: ReadonlyMap<AnalysisStepKey, string> = new Map([
  ["measuring", "Measuring your features"],
  ["writing", "Writing your report"],
  ["generating_images", "Creating your images"],
  ["assembling", "Putting your report together"],
]);

/** The step's name in plain words. */
export function stepLabel(step: AnalysisStepKey): string {
  return STEP_LABELS.get(step) ?? step;
}

export const STATE_TEXT: Record<AnalysisStepState, string> = {
  done: "Done",
  current: "In progress",
  waiting: "Waiting",
  failed: "Didn't finish",
};

export const READY_ANNOUNCEMENT = "Your report is ready.";
export const FAILED_ANNOUNCEMENT = "Your analysis didn't finish. You'll find your options below.";

/** What a screen reader hears when the current step changes (never moves focus). */
export function stepAnnouncement(step: AnalysisStepKey): string {
  return `Now: ${stepLabel(step)}.`;
}

/** The leave-and-come-back note with the configured expected wait (AC7.2.2). */
export function leaveNote(minutes: number): string {
  return `This can take up to about ${minutes} ${minutes === 1 ? "minute" : "minutes"}. You can close this page and come back later: we'll keep going, and your progress will be here.`;
}

/** Codes that mean the photo set must be fixed before the analysis can start (AC7.1.2). */
export function needsPhotos(error: ApiError): boolean {
  return error.code === "PHOTO_IDENTITY_MISMATCH" || error.code === "PHOTO_SET_INCOMPLETE";
}

/** A user-facing message for an analysis API error. */
export function analysisErrorMessage(error: ApiError): string {
  switch (error.code) {
    case "PHOTO_IDENTITY_MISMATCH":
      return "Your photos don't appear to show the same person any more. Please retake the highlighted photo to start your analysis.";
    case "PHOTO_SET_INCOMPLETE":
      return "Please add a photo for every angle to start your analysis.";
    case "PAYMENT_REQUIRED":
      return "Please complete your payment first.";
    case "RERUN_NOT_AVAILABLE":
      return "A free re-run isn't available for this analysis.";
    default:
      return messageFor(error);
  }
}
