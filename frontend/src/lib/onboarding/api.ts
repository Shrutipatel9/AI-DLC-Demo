// Onboarding endpoints (contract C1 /onboarding/*; US4.1-US4.4). UI code never imports the
// API client (FE-004); it calls these functions through `@/lib/onboarding`.
import { apiRequest } from "@/lib/api/client";
import { isApiError } from "@/lib/api/errors";
import type { components } from "@/lib/api/types.gen";

type Schemas = components["schemas"];

export type ConsentState = Schemas["ConsentState"];
export type QuestionnaireDefinition = Schemas["QuestionnaireDefinitionOut"];
export type Question = Schemas["QuestionOut"];
export type QuestionnaireProgress = Schemas["QuestionnaireProgress"];
export type SavedAnswer = Schemas["SavedAnswerOut"];
export type AnswerValue = Schemas["AnswerInput"]["value"];

/** Where the user is in onboarding (drives the home page link). */
export type OnboardingStatus = "not_started" | "in_progress" | "submitted";

export function getConsent(): Promise<ConsentState> {
  return apiRequest<ConsentState>("/onboarding/consent");
}

export function giveConsent(consentTextVersion: string): Promise<ConsentState> {
  return apiRequest<ConsentState>("/onboarding/consent", {
    method: "POST",
    body: { consentTextVersion },
  });
}

export function getQuestionnaire(): Promise<QuestionnaireDefinition> {
  return apiRequest<QuestionnaireDefinition>("/onboarding/questionnaire");
}

export function getProgress(): Promise<QuestionnaireProgress> {
  return apiRequest<QuestionnaireProgress>("/onboarding/response");
}

export function saveAnswer(
  questionId: string,
  value: AnswerValue,
  followUpText: string | null,
): Promise<QuestionnaireProgress> {
  return apiRequest<QuestionnaireProgress>(
    `/onboarding/response/answers/${encodeURIComponent(questionId)}`,
    { method: "PUT", body: { value, followUpText } },
  );
}

export function submitQuestionnaire(disclaimerConfirmed: boolean): Promise<QuestionnaireProgress> {
  return apiRequest<QuestionnaireProgress>("/onboarding/response/submit", {
    method: "POST",
    body: { disclaimerConfirmed },
  });
}

/** Consent first, then the response: not started, in progress or submitted. */
export async function loadOnboardingStatus(): Promise<OnboardingStatus> {
  const consent = await getConsent();
  if (!consent.given) return "not_started";
  try {
    const progress = await getProgress();
    if (progress.submitted) return "submitted";
    return Object.keys(progress.answers).length > 0 ? "in_progress" : "not_started";
  } catch (error) {
    // The consent text changed between the two calls: the user must consent again.
    if (isApiError(error) && error.code === "CONSENT_REQUIRED") return "not_started";
    throw error;
  }
}
