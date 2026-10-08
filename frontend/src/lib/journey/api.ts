// The journey endpoint (contract C1 /journey/next-step; US11.8). UI code never imports the API
// client (FE-004); it calls these functions through `@/lib/journey`.
import { apiRequest } from "@/lib/api/client";
import type { components } from "@/lib/api/types.gen";

export type NextStep = components["schemas"]["NextStepOut"];
export type Step = NextStep["step"];

/** The one next unfinished step, recomputed by the server on every call. */
export function getNextStep(): Promise<NextStep> {
  return apiRequest<NextStep>("/journey/next-step");
}
