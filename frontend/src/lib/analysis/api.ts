// Analysis endpoints (contract C1 /analysis/runs; US7.1, US7.2, US7.11). UI code never imports
// the API client (FE-004); it calls these functions through `@/lib/analysis`.
import { apiRequest } from "@/lib/api/client";
import type { components } from "@/lib/api/types.gen";

export type AnalysisRun = components["schemas"]["AnalysisRunOut"];
export type AnalysisStepKey = AnalysisRun["steps"][number]["key"];
export type AnalysisStepState = AnalysisRun["steps"][number]["state"];

/** "Start Analysis": idempotent, a second call returns the same run (AC7.1.3). */
export function startAnalysis(): Promise<AnalysisRun> {
  return apiRequest<AnalysisRun>("/analysis/runs", { method: "POST" });
}

/** The current run's steps and state (404 NOT_FOUND when none was started). */
export function getCurrentRun(): Promise<AnalysisRun> {
  return apiRequest<AnalysisRun>("/analysis/runs/current");
}

/** The one free re-run after a failed run (US7.11). */
export function rerunAnalysis(): Promise<AnalysisRun> {
  return apiRequest<AnalysisRun>("/analysis/runs/current/rerun", { method: "POST" });
}
