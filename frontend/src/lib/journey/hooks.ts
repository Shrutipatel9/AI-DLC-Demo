"use client";

// The route guard and the "go to my next step" action (US11.8, US5.7, US2.1). The server decides
// the step on every call (AC11.8.1); this code only follows it. The guard asks once when a page
// opens, so a decision such as skipping the photo review is taken on the first page load only
// ([IV] §6, AC5.7.2).
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { getNextStep } from "./api";
import { isTooEarly, routeForStep, type JourneyStage } from "./routes";

export type GuardState = "checking" | "allowed";

/**
 * Sends the user to their next step when this page is a later step; otherwise lets it render.
 * When the next step cannot be read the page renders anyway and reports its own error.
 */
export function useJourneyGuard(stage: JourneyStage): GuardState {
  const router = useRouter();
  const [state, setState] = useState<GuardState>("checking");

  useEffect(() => {
    let active = true;
    getNextStep()
      .then((next) => {
        if (!active) return;
        if (isTooEarly(stage, next.step)) router.replace(routeForStep(next.step));
        else setState("allowed");
      })
      .catch(() => {
        if (active) setState("allowed");
      });
    return () => {
      active = false;
    };
  }, [stage, router]);

  return state;
}

/** Returns a function that opens the user's next unfinished step (AC2.1.3). */
export function useGoToNextStep(): () => Promise<void> {
  const router = useRouter();
  return useCallback(async () => {
    try {
      const next = await getNextStep();
      router.push(routeForStep(next.step));
    } catch {
      router.push("/home"); // the home page's own guard then finds the step
    }
  }, [router]);
}
