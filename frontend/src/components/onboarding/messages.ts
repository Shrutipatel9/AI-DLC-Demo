// Plain-language messages for the onboarding screens (the UI branches on `code` only).
import { messageFor } from "@/components/auth/messages";
import type { ApiError } from "@/lib/api/errors";

export const CHOOSE_ANSWER = "Please choose an answer.";
export const ENTER_ANSWER = "Please enter an answer.";
export const SAVE_FAILED = "We couldn't save your answer. Please try again.";
export const CONSENT_CHANGED = "The consent text has changed. Please read it again.";

/** The toast text for an onboarding API failure. */
export function onboardingMessage(error: ApiError): string {
  switch (error.code) {
    case "CONSENT_REQUIRED":
      return CONSENT_CHANGED;
    case "DISCLAIMER_REQUIRED":
      return "Please confirm the statement above to submit.";
    case "QUESTIONNAIRE_ALREADY_SUBMITTED":
      return "Your questionnaire is already submitted.";
    case "VALIDATION_FAILED":
      return "Please check your answer and try again.";
    default:
      return messageFor(error);
  }
}
