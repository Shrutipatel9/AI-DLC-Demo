// Plain-language messages for the payment screens. The UI branches on error codes only.
import { messageFor } from "@/components/auth/messages";
import type { ApiError } from "@/lib/api/errors";

export const START_ANALYSIS_NOTE =
  "Your analysis doesn't start on its own: it starts only when you click Start Analysis.";

export const STILL_CONFIRMING =
  "Your payment is still being confirmed. You won't be charged twice, and you can safely leave this page and come back later.";

export const CONFIRMED_ANNOUNCEMENT = "Your payment is confirmed. You can start your analysis.";

export const START_ANALYSIS_LOCKED = "Available once your payment is confirmed.";

/** Codes that mean the photo set must be fixed before paying (BR-005, AC6.2.2). */
export function needsPhotos(error: ApiError): boolean {
  return error.code === "PHOTO_IDENTITY_MISMATCH" || error.code === "PHOTO_SET_INCOMPLETE";
}

/** A user-facing message for a payment API error. */
export function paymentErrorMessage(error: ApiError): string {
  switch (error.code) {
    case "PHOTO_IDENTITY_MISMATCH":
      return "Your photos don't appear to show the same person any more. Please retake the highlighted photo before paying.";
    case "PHOTO_SET_INCOMPLETE":
      return "Please add a photo for every angle before paying.";
    case "ALREADY_PAID":
      return "You've already paid for your report.";
    case "UPSTREAM_UNAVAILABLE":
    case "UPSTREAM_TIMEOUT":
      return "We couldn't reach the payment service. You have not been charged. Please try again.";
    default:
      return messageFor(error);
  }
}
