// Which page shows each journey step, and how far along each page is (US11.8, AC11.8.2).
import type { Step } from "./api";

/**
 * The position of a page in the journey. A page is "later" than the user's next step when its
 * stage is higher, and then the guard sends the user to their next step.
 */
export type JourneyStage = 1 | 2 | 3 | 4 | 5 | 6;

export const STAGE = {
  onboarding: 1,
  photos: 2,
  payment: 3,
  confirming: 4,
  analysis: 5,
  home: 6,
} as const satisfies Record<string, JourneyStage>;

/** The page that shows each step. */
export function routeForStep(step: Step): string {
  switch (step) {
    case "consent":
    case "questionnaire":
      return "/onboarding";
    case "photos":
      return "/photos";
    case "payment":
      return "/payment";
    case "confirming_payment":
      return "/payment/success";
    case "start_analysis":
    case "progress":
      return "/analysis";
    case "home":
      return "/home";
  }
}

function stageForStep(step: Step): JourneyStage {
  switch (step) {
    case "consent":
    case "questionnaire":
      return STAGE.onboarding;
    case "photos":
      return STAGE.photos;
    case "payment":
      return STAGE.payment;
    case "confirming_payment":
      return STAGE.confirming;
    case "start_analysis":
    case "progress":
      return STAGE.analysis;
    case "home":
      return STAGE.home;
  }
}

/** True when a page at `stage` is opened before the user's next step has been reached. */
export function isTooEarly(stage: JourneyStage, next: Step): boolean {
  return stage > stageForStep(next);
}
