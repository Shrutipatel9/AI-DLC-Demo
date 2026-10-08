// Loading the report and the Home data (US8.7, US11.1).
//
// - `phase` is "loading" until the first answer, "none" when there is no report to show (402
//   before payment, 404 REPORT_NOT_READY before the analysis finished), "error" for anything else,
//   then "ready".
import { useCallback, useEffect, useState } from "react";

import { isApiError } from "@/lib/api/errors";

import { getHome, getReport, loadReportPdf, type Home, type Report } from "./api";
import { PDF_FILE_NAME, saveBlob } from "./download";

export type LoadPhase = "loading" | "none" | "error" | "ready";

export interface Loaded<T> {
  phase: LoadPhase;
  data: T | null;
  /** Read again now (the "Try again" button). */
  reload: () => void;
}

interface State<T> {
  phase: LoadPhase;
  data: T | null;
}

function useLoaded<T>(load: () => Promise<T>): Loaded<T> {
  const [state, setState] = useState<State<T>>({ phase: "loading", data: null });
  const [generation, setGeneration] = useState(0);

  useEffect(() => {
    let active = true;
    load()
      .then((data) => {
        if (active) setState({ phase: "ready", data });
      })
      .catch((error: unknown) => {
        if (!active) return;
        const missing =
          isApiError(error) &&
          (error.code === "REPORT_NOT_READY" || error.code === "PAYMENT_REQUIRED");
        setState({ phase: missing ? "none" : "error", data: null });
      });
    return () => {
      active = false;
    };
  }, [load, generation]);

  const reload = useCallback(() => {
    setState({ phase: "loading", data: null });
    setGeneration((value) => value + 1);
  }, []);
  return { phase: state.phase, data: state.data, reload };
}

export function useReport(): Loaded<Report> {
  return useLoaded(getReport);
}

export function useHome(): Loaded<Home> {
  return useLoaded(getHome);
}

/** Download the report PDF; resolves true on success, false when it could not be fetched. */
export async function downloadReportPdf(): Promise<boolean> {
  try {
    saveBlob(await loadReportPdf(), PDF_FILE_NAME);
    return true;
  } catch {
    return false;
  }
}
