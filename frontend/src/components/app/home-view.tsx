"use client";

import { ArrowRight, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { toast } from "@/components/feedback/toast";
import { HomeOverview } from "@/components/home/home-overview";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useAuth, useAuthActions } from "@/lib/auth";
import { useGoToNextStep } from "@/lib/journey";
import { useHome } from "@/lib/report";

import { AppShell } from "./app-shell";

// Signed-in home. Rendered inside ProtectedRoute, so the session is restored before it shows
// (U2 WF-U2-2) and the journey guard has already sent anyone without a report to their next
// step (U10, US11.8). The greeting is refreshed from "who am I" (AC3.8.1). Once a report exists
// it is the Home Overview (U8, US11.1); if the Home data cannot be read it keeps the screen
// below, which offers the journey's next step.
export function HomeView() {
  const { user } = useAuth();
  const { loadCurrentUser } = useAuthActions();
  const home = useHome();
  const goToNextStep = useGoToNextStep();
  const [loaded, setLoaded] = useState(false);

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
      <Card className="mx-auto max-w-[720px] text-center">
        <span
          aria-hidden="true"
          className="mx-auto mb-4 inline-flex size-14 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-raised"
        >
          <Sparkles className="size-7" />
        </span>
        <h1 className="text-2xl font-bold text-heading sm:text-3xl" data-testid="home-greeting">
          Hi, {user?.fullName}
        </h1>
        <p className="mt-2 text-base text-subheading" data-testid="home-status" aria-live="polite">
          {!loaded
            ? "Loading your account…"
            : home.phase === "loading"
              ? "Loading your overview…"
              : "Your overview isn't ready yet. Pick up where you left off."}
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Button onClick={() => void goToNextStep()} data-testid="home-next-step-button">
            Continue
            <ArrowRight aria-hidden="true" />
          </Button>
          <Link
            href="/visuals"
            className={buttonVariants({ variant: "secondary" })}
            data-testid="home-visuals-link"
          >
            AI Visuals
          </Link>
        </div>
      </Card>
    </AppShell>
  );
}
