// Following the analysis (US7.2). The progress screen polls GET /analysis/runs/current (contract:
// every 2-3 s) while the run is going, stops when it completes or fails, and starts again after
// the free re-run. Coming back later (a new page load) simply reads the same run (AC7.2.3).
//
// - `phase` is "loading" until the first answer, "none" when no analysis was started (404),
//   "error" when the first read failed, then the run's own status;
// - a failed poll after the first answer keeps the last known run and tries again on the next tick.
import { useCallback, useEffect, useRef, useState } from "react";

import { isApiError } from "@/lib/api/errors";

import { getCurrentRun, rerunAnalysis, type AnalysisRun } from "./api";

export const POLL_INTERVAL_MS = 2_000;

export type ProgressPhase = "loading" | "none" | "error" | AnalysisRun["status"];

export interface Progress {
  phase: ProgressPhase;
  run: AnalysisRun | null;
  /** Read the run again now (the "Try again" button after a load error). */
  reload: () => void;
  /** The free re-run; resolves true when it started, false when the server refused it. */
  rerun: () => Promise<boolean>;
}

interface State {
  phase: ProgressPhase;
  run: AnalysisRun | null;
}

export function useAnalysisProgress(intervalMs: number = POLL_INTERVAL_MS): Progress {
  const [state, setState] = useState<State>({ phase: "loading", run: null });
  const [generation, setGeneration] = useState(0);
  const hasRun = useRef(false);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      let again = true;
      try {
        const run = await getCurrentRun();
        if (!active) return;
        hasRun.current = true;
        setState({ phase: run.status, run });
        again = run.status === "running";
      } catch (error) {
        if (!active) return;
        if (isApiError(error) && error.code === "NOT_FOUND") {
          setState({ phase: "none", run: null });
          again = false;
        } else if (!hasRun.current) {
          setState({ phase: "error", run: null });
          again = false;
        }
      }
      if (active && again) timer = setTimeout(() => void poll(), intervalMs);
    };
    void poll();

    return () => {
      active = false;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [intervalMs, generation]);

  const reload = useCallback(() => {
    setState({ phase: "loading", run: null });
    hasRun.current = false;
    setGeneration((value) => value + 1);
  }, []);

  const rerun = useCallback(async () => {
    try {
      const run = await rerunAnalysis();
      hasRun.current = true;
      setState({ phase: run.status, run });
      setGeneration((value) => value + 1);
      return true;
    } catch {
      return false;
    }
  }, []);

  return { phase: state.phase, run: state.run, reload, rerun };
}
