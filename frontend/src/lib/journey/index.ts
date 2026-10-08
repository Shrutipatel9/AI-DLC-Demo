// The only journey entry point for UI code (FE-004: UI never imports the API client).
export { getNextStep, type NextStep, type Step } from "./api";
export { useGoToNextStep, useJourneyGuard, type GuardState } from "./hooks";
export { STAGE, isTooEarly, routeForStep, type JourneyStage } from "./routes";
