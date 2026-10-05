// A small, stateful stand-in for the /onboarding/* API (contract C1), used with
// `mockFetch` in component tests. It mirrors the server rules the UI relies on: consent gate,
// branching (showIf), follow-ups, required checks and the disclaimer. Test-only module.
import type { components } from "@/lib/api/types.gen";

import { errorResponse, jsonResponse, type RecordedRequest } from "./fetch-mock";

type Definition = components["schemas"]["QuestionnaireDefinitionOut"];
type Question = components["schemas"]["QuestionOut"];
type Saved = components["schemas"]["SavedAnswerOut"];

export const DISCLAIMER = "I hereby confirm that I do not have any concerns (test wording).";

export const TEST_DEFINITION: Definition = {
  definitionVersion: "qs-test",
  disclaimerText: DISCLAIMER,
  questions: [
    {
      id: "q1",
      order: 1,
      text: "What is your occupation?",
      type: "text",
      required: true,
      placeholder: "e.g. Entrepreneur",
      maxLength: 500,
    },
    {
      id: "q4",
      order: 4,
      text: "Would you rather look more masculine or more feminine?",
      type: "single",
      required: true,
      options: [
        { value: "masculine", label: "Masculine" },
        { value: "feminine", label: "Feminine" },
        { value: "no_preference", label: "No Preference" },
      ],
    },
    {
      id: "q7",
      order: 7,
      text: "Please select all treatment types you are comfortable undergoing:",
      type: "multi",
      required: false,
      options: [
        { value: "botox", label: "Botox", group: "Injectables (minimally invasive)" },
        { value: "laser", label: "Laser", group: "Non-invasive treatments" },
        { value: "ultrasound", label: "Ultrasound", group: "Non-invasive treatments" },
      ],
    },
    {
      id: "q9",
      order: 9,
      text: "Are you taking any medications (prescription or over-the-counter)?",
      type: "yesno",
      required: true,
      followUp: {
        showWhen: true,
        type: "text",
        label: "Please list your medications",
        maxLength: 2000,
      },
    },
    {
      id: "q19",
      order: 19,
      text: "Can you grow a full beard?",
      type: "yesno",
      required: true,
      showIf: { questionId: "q4", anyOf: ["masculine", "no_preference"] },
    },
    {
      id: "q23",
      order: 23,
      text: "Anything else you think we should know?",
      type: "text",
      required: false,
      maxLength: 2000,
    },
  ],
};

export interface OnboardingServerState {
  consentGiven: boolean;
  consentVersion: string;
  answers: Record<string, Saved>;
  submitted: boolean;
  definition: Definition;
}

export function newState(overrides: Partial<OnboardingServerState> = {}): OnboardingServerState {
  return {
    consentGiven: false,
    consentVersion: "consent-v1",
    answers: {},
    submitted: false,
    definition: TEST_DEFINITION,
    ...overrides,
  };
}

function visibleIds(state: OnboardingServerState): string[] {
  const shown: string[] = [];
  for (const question of state.definition.questions) {
    const rule = question.showIf;
    if (rule) {
      const parent = new Map(Object.entries(state.answers)).get(rule.questionId);
      if (
        !shown.includes(rule.questionId) ||
        !parent ||
        !rule.anyOf.includes(parent.value as never)
      )
        continue;
    }
    shown.push(question.id);
  }
  return shown;
}

function progress(state: OnboardingServerState) {
  return {
    answers: state.answers,
    visibleQuestionIds: visibleIds(state),
    submitted: state.submitted,
    submittedAt: state.submitted ? "2026-10-01T10:00:00Z" : null,
  };
}

function consent(state: OnboardingServerState) {
  return {
    consentTextVersion: state.consentVersion,
    consentText:
      "How we use your photos and answers\nPhotos are used only for your report.\nHealth answers never go to the AI service.",
    agreementText: "I agree to the processing of my facial images for my report.",
    given: state.consentGiven,
    givenAt: state.consentGiven ? "2026-10-01T10:00:00Z" : null,
  };
}

function answered(question: Question, saved: Saved | undefined): boolean {
  if (!saved) return !question.required;
  if (typeof saved.value === "string") return saved.value.trim() !== "" || !question.required;
  if (Array.isArray(saved.value)) return saved.value.length > 0 || !question.required;
  return true;
}

/** A `mockFetch` handler serving the onboarding API from `state` (mutated in place). */
export function onboardingServer(state: OnboardingServerState) {
  return (request: RecordedRequest): Response | undefined => {
    const path = new URL(request.url, "http://x").pathname;
    if (!path.startsWith("/onboarding/")) return undefined;
    if (path === "/onboarding/consent") {
      if (request.method === "GET") return jsonResponse(200, consent(state));
      const body = request.body as { consentTextVersion: string };
      if (body.consentTextVersion !== state.consentVersion)
        return errorResponse(409, "CONSENT_REQUIRED");
      state.consentGiven = true;
      return jsonResponse(201, consent(state));
    }
    if (!state.consentGiven) return errorResponse(403, "CONSENT_REQUIRED");
    if (path === "/onboarding/questionnaire") return jsonResponse(200, state.definition);
    if (path === "/onboarding/response") return jsonResponse(200, progress(state));
    if (state.submitted) return errorResponse(409, "QUESTIONNAIRE_ALREADY_SUBMITTED");
    if (path.startsWith("/onboarding/response/answers/")) {
      const id = decodeURIComponent(path.split("/").at(-1) ?? "");
      const body = request.body as { value: Saved["value"]; followUpText: string | null };
      state.answers = {
        ...state.answers,
        [id]: { value: body.value, followUpText: body.followUpText },
      };
      return jsonResponse(200, progress(state));
    }
    if (path === "/onboarding/response/submit") {
      const ids = visibleIds(state);
      const byId = new Map(Object.entries(state.answers));
      const missing = state.definition.questions.filter(
        (question) => ids.includes(question.id) && !answered(question, byId.get(question.id)),
      );
      if (missing.length > 0)
        return errorResponse(422, "VALIDATION_FAILED", {
          details: missing.map((question) => ({ field: question.id, reason: "REQUIRED" })),
        });
      if (!(request.body as { disclaimerConfirmed?: boolean }).disclaimerConfirmed)
        return errorResponse(422, "DISCLAIMER_REQUIRED");
      state.submitted = true;
      return jsonResponse(200, progress(state));
    }
    return undefined;
  };
}
