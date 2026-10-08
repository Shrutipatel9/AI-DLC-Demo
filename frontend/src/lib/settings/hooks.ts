"use client";

import { useCallback, useEffect, useState } from "react";

import { getAccountInfo, getBilling, type AccountInfo, type Billing } from "./api";

export type LoadPhase = "loading" | "error" | "ready";

export interface Loaded<T> {
  phase: LoadPhase;
  data: T | null;
  /** Read again now (the "Try again" button). */
  reload: () => void;
}

function useLoaded<T>(load: () => Promise<T>): Loaded<T> {
  const [state, setState] = useState<{ phase: LoadPhase; data: T | null }>({
    phase: "loading",
    data: null,
  });
  const [generation, setGeneration] = useState(0);

  useEffect(() => {
    let active = true;
    load()
      .then((data) => {
        if (active) setState({ phase: "ready", data });
      })
      .catch(() => {
        if (active) setState({ phase: "error", data: null });
      });
    return () => {
      active = false;
    };
  }, [load, generation]);

  const reload = useCallback(() => {
    setState({ phase: "loading", data: null });
    setGeneration((value) => value + 1);
  }, []);

  return { ...state, reload };
}

export function useAccountInfo(): Loaded<AccountInfo> {
  return useLoaded(getAccountInfo);
}

export function useBilling(): Loaded<Billing> {
  return useLoaded(getBilling);
}
