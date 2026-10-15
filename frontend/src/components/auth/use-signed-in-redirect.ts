"use client";

// Signed-in visitors never see the sign-in forms: once the session is known to be signed in
// (and no code is waiting to be entered), they are taken to their next unfinished step
// (US11.8) while the full-page loader covers the screen, so no form flashes on the way.
import { useEffect, useRef } from "react";

import { useAuth } from "@/lib/auth";
import { useGoToNextStep } from "@/lib/journey";

/**
 * Returns true while a signed-in visitor is being sent on; the caller renders the loader.
 * `markNavigating` lets a form that starts its own navigation (the code form) say so, so the
 * user is not sent twice.
 */
export function useSignedInRedirect(): { redirecting: boolean; markNavigating: () => void } {
  const { status, pending } = useAuth();
  const goToNextStep = useGoToNextStep();
  const navigating = useRef(false);
  const redirecting = status === "signedIn" && pending === null;

  useEffect(() => {
    if (!redirecting || navigating.current) return;
    navigating.current = true;
    void goToNextStep();
  }, [redirecting, goToNextStep]);

  return {
    redirecting,
    markNavigating: () => {
      navigating.current = true;
    },
  };
}
