"use client";

// Guards signed-in pages (BR6.1): waits while the session is restored, sends a signed-out
// visitor to /login, and renders the page once signed in. A page that belongs to a step of the
// journey passes its `stage`; opening it before an earlier step is finished sends the user to
// their next step (US11.8, AC11.8.2).
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth, useAuthActions } from "@/lib/auth";
import { useJourneyGuard, type JourneyStage } from "@/lib/journey";

import { FullPageLoader } from "./full-page-loader";
import { PageLoader } from "./page-loader";

function JourneyGate({ stage, children }: { stage: JourneyStage; children: ReactNode }) {
  const state = useJourneyGuard(stage);
  if (state === "checking") {
    return (
      <main id="main">
        <PageLoader message="Finding your next step…" testId="journey-loader" />
      </main>
    );
  }
  return <>{children}</>;
}

export function ProtectedRoute({ children, stage }: { children: ReactNode; stage?: JourneyStage }) {
  const router = useRouter();
  const { status, restoreFailed } = useAuth();
  const { restore } = useAuthActions();

  useEffect(() => {
    if (status === "signedOut") router.replace("/login");
  }, [status, router]);

  if (status === "signedOut") {
    // On the way to the login page (after logging out or an expired session).
    return (
      <main id="main">
        <PageLoader message="Taking you to sign in…" testId="signout-loader" />
      </main>
    );
  }
  if (status !== "signedIn") {
    return <FullPageLoader failed={restoreFailed} onRetry={() => void restore()} />;
  }
  if (stage !== undefined) return <JourneyGate stage={stage}>{children}</JourneyGate>;
  return <>{children}</>;
}
