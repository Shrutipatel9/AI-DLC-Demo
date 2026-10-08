// A small, scripted stand-in for the /analysis API (contract C1), used with `mockFetch` in
// component tests. `runs` are answered in order by GET /analysis/runs/current (the last one
// repeats), so a test can script "current, current, completed" the way the worker would.
// Test-only module.
import type { components } from "@/lib/api/types.gen";

import { errorResponse, jsonResponse, type RecordedRequest } from "./fetch-mock";

export type Run = components["schemas"]["AnalysisRunOut"];
type StepState = Run["steps"][number]["state"];

const KEYS = ["measuring", "writing", "generating_images", "assembling"] as const;

/** A run with the four steps in the given states (done, current, waiting, failed). */
export function makeRun(
  states: [StepState, StepState, StepState, StepState],
  overrides: Partial<Run> = {},
): Run {
  const failed = states.includes("failed");
  const complete = states.every((state) => state === "done");
  return {
    runId: "11111111-1111-4111-8111-111111111111",
    status: failed ? "failed" : complete ? "completed" : "running",
    steps: KEYS.map((key, index) => ({ key, state: states.at(index) ?? "waiting" })),
    rerunAvailable: false,
    failureMessage: null,
    contactSupport: false,
    expectedWaitMinutes: 8,
    ...overrides,
  };
}

export const RUNNING = makeRun(["current", "waiting", "waiting", "waiting"]);
export const WRITING = makeRun(["done", "current", "waiting", "waiting"]);
export const COMPLETED = makeRun(["done", "done", "done", "done"]);
export const FAILED = makeRun(["done", "failed", "waiting", "waiting"], {
  rerunAvailable: true,
  failureMessage:
    "Something went wrong on our side while preparing your report. Your payment still covers this report, and you can try again for free.",
});
export const FAILED_TWICE = makeRun(["done", "failed", "waiting", "waiting"], {
  contactSupport: true,
  failureMessage:
    "Something went wrong on our side again. Your payment still covers this report. Please contact support and we will sort it out.",
});

type Answer = Run | { status: number; code: string };

export interface AnalysisServerState {
  /** Answers of GET /analysis/runs/current in order; empty means 404 (no run). */
  runs: Run[];
  /** What POST /analysis/runs answers: a run, or an error. */
  start: Answer;
  /** What POST /analysis/runs/current/rerun answers. */
  rerun: Answer;
  starts: number;
  reruns: number;
  /** When true, GET /analysis/runs/current fails with 500. */
  failReads: boolean;
}

export function newAnalysisState(
  overrides: Partial<AnalysisServerState> = {},
): AnalysisServerState {
  return {
    runs: [RUNNING],
    start: RUNNING,
    rerun: RUNNING,
    starts: 0,
    reruns: 0,
    failReads: false,
    ...overrides,
  };
}

function answer(value: Answer, ok: number): Response {
  return "runId" in value ? jsonResponse(ok, value) : errorResponse(value.status, value.code);
}

/** A `mockFetch` handler serving the three /analysis routes. */
export function analysisServer(state: AnalysisServerState) {
  return (request: RecordedRequest): Response | undefined => {
    const path = new URL(request.url, "http://x").pathname;
    if (!path.startsWith("/analysis/")) return undefined;
    if (request.method === "POST" && path === "/analysis/runs") {
      state.starts += 1;
      return answer(state.start, 202);
    }
    if (request.method === "POST" && path === "/analysis/runs/current/rerun") {
      state.reruns += 1;
      return answer(state.rerun, 202);
    }
    if (request.method === "GET" && path === "/analysis/runs/current") {
      if (state.failReads) return errorResponse(500, "INTERNAL_ERROR");
      if (state.runs.length === 0) return errorResponse(404, "NOT_FOUND");
      const next = state.runs.length > 1 ? state.runs.shift()! : state.runs[0];
      return jsonResponse(200, next);
    }
    return undefined;
  };
}
