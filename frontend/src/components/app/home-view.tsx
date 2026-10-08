"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { toast } from "@/components/feedback/toast";
import { HomeOverview } from "@/components/home/home-overview";
import { Card } from "@/components/ui/card";
import { useAuth, useAuthActions } from "@/lib/auth";
import { loadOnboardingStatus, type OnboardingStatus } from "@/lib/onboarding";
import { useHome } from "@/lib/report";

import { AppShell } from "./app-shell";

function onboardingLinkText(status: OnboardingStatus | null): string {
  if (status === "in_progress") return "Continue your questionnaire";
  if (status === "not_started") return "Start your questionnaire";
  return "Go to your questionnaire";
}

// Signed-in home. Rendered inside ProtectedRoute, so the session is restored before it
// shows (U2 WF-U2-2). The greeting is refreshed from "who am I" (AC3.8.1). Until the
// questionnaire is submitted it links to onboarding (U3 plan Step 4); after that it links to
// the photo step (U4 plan Step 8, temporary until the Journey in U10). Once a report exists it
// becomes the Home Overview (U8, US11.1); a 402/404 from /home keeps the screen below.
export function HomeView() {
  const { user } = useAuth();
  const { loadCurrentUser } = useAuthActions();
  const home = useHome();
  const [loaded, setLoaded] = useState(false);
  // `null` while loading or when the status could not be read: the link is still shown,
  // because onboarding itself reports any error.
  const [onboarding, setOnboarding] = useState<OnboardingStatus | null>(null);

  useEffect(() => {
    let active = true;
    loadCurrentUser()
      .then(() => {
        if (active) setLoaded(true);
      })
      .catch(() => {
        if (!active) return;
        setLoaded(true);
        toast.error("We couldn't load your account. Please try again.");
      });
    loadOnboardingStatus()
      .then((status) => {
        if (active) setOnboarding(status);
      })
      .catch(() => {
        if (active) setOnboarding(null);
      });
    return () => {
      active = false;
    };
  }, [loadCurrentUser]);

  if (home.phase === "ready" && home.data) {
    return (
      <AppShell>
        <HomeOverview home={home.data} name={user?.fullName ?? ""} />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <Card>
        <h1 className="text-2xl font-bold text-heading" data-testid="home-greeting">
          Hi, {user?.fullName}
        </h1>
        <p className="mt-2 text-base text-muted" data-testid="home-status" aria-live="polite">
          {!loaded
            ? "Loading your account…"
            : onboarding === "submitted"
              ? "Your questionnaire is submitted. Next, add your photos."
              : "Your account is ready. Next, tell us about yourself."}
        </p>
        {onboarding === "submitted" ? (
          // Temporary entry point until the Journey (U10) routes to the next step.
          <Link
            href="/photos"
            className="mt-6 inline-flex min-h-11 items-center justify-center rounded-[var(--radius)] bg-accent-strong px-4 text-base font-semibold text-white hover:bg-[#1f6159]"
            data-testid="home-photos-link"
          >
            Add your photos
          </Link>
        ) : (
          <Link
            href="/onboarding"
            className="mt-6 inline-flex min-h-11 items-center justify-center rounded-[var(--radius)] bg-accent-strong px-4 text-base font-semibold text-white hover:bg-[#1f6159]"
            data-testid="home-onboarding-link"
          >
            {onboardingLinkText(onboarding)}
          </Link>
        )}
        <Link
          href="/visuals"
          className="mt-3 inline-flex min-h-11 items-center justify-center rounded-[var(--radius)] border border-card-border bg-white px-4 text-base font-semibold text-heading hover:bg-[#eef2f5]"
          data-testid="home-visuals-link"
        >
          AI Visuals
        </Link>
      </Card>
    </AppShell>
  );
}
