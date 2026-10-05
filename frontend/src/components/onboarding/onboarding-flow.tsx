"use client";

// Onboarding: consent, then the questionnaire (US4.1-US4.4). Loads the consent state; once
// consent is given it loads the definition and the saved answers (resume, AC4.2.6).
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { toast } from "@/components/feedback/toast";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { isApiError } from "@/lib/api/errors";
import {
  getConsent,
  getProgress,
  getQuestionnaire,
  type ConsentState,
  type QuestionnaireDefinition,
  type QuestionnaireProgress,
} from "@/lib/onboarding";

import { ConsentStep } from "./consent-step";
import { onboardingMessage } from "./messages";
import { QuestionnaireWizard } from "./questionnaire-wizard";

type Stage =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "consent"; consent: ConsentState }
  | {
      kind: "questionnaire";
      definition: QuestionnaireDefinition;
      progress: QuestionnaireProgress;
    }
  | { kind: "submitted" };

const STEP_LABEL: Record<"consent" | "questionnaire", string> = {
  consent: "Step 1 of 5 · Consent",
  questionnaire: "Step 2 of 5 · Questionnaire",
};

async function fetchStage(): Promise<Stage> {
  try {
    const consent = await getConsent();
    if (!consent.given) return { kind: "consent", consent };
    const [definition, progress] = await Promise.all([getQuestionnaire(), getProgress()]);
    return progress.submitted
      ? { kind: "submitted" }
      : { kind: "questionnaire", definition, progress };
  } catch (error) {
    if (!isApiError(error)) throw error;
    toast.error(onboardingMessage(error));
    return { kind: "error" };
  }
}

export function OnboardingFlow() {
  const router = useRouter();
  const [stage, setStage] = useState<Stage>({ kind: "loading" });

  const reload = useCallback(() => {
    setStage({ kind: "loading" });
    void fetchStage().then(setStage);
  }, []);

  useEffect(() => {
    let active = true;
    void fetchStage().then((next) => {
      if (active) setStage(next);
    });
    return () => {
      active = false;
    };
  }, []);

  if (stage.kind === "loading") {
    return (
      <p role="status" className="text-base text-muted" data-testid="onboarding-loading">
        Loading your questionnaire…
      </p>
    );
  }
  if (stage.kind === "error") {
    return (
      <div className="space-y-4" data-testid="onboarding-error">
        <p role="alert" className="text-base text-heading">
          We couldn&apos;t load the questionnaire. Please try again.
        </p>
        <Button onClick={reload} data-testid="onboarding-retry-button">
          Try again
        </Button>
      </div>
    );
  }
  if (stage.kind === "submitted") {
    return (
      <div className="space-y-4" data-testid="onboarding-submitted">
        <h1 className="text-2xl font-bold text-heading">Your questionnaire is submitted</h1>
        <p className="text-base text-foreground">Thank you. Next, add your photos.</p>
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => router.push("/photos")} data-testid="onboarding-photos-button">
            Add your photos
          </Button>
          <Button
            variant="secondary"
            onClick={() => router.push("/home")}
            data-testid="onboarding-home-button"
          >
            Go to home
          </Button>
        </div>
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-[640px]">
      <p className="mb-3 text-sm font-medium text-muted" data-testid="onboarding-step">
        {STEP_LABEL[stage.kind]}
      </p>
      <Card>
        {stage.kind === "consent" ? (
          <ConsentStep
            key={stage.consent.consentTextVersion}
            consent={stage.consent}
            onConsented={reload}
            onTextChanged={reload}
          />
        ) : (
          <>
            <h1 className="sr-only">Questionnaire</h1>
            <QuestionnaireWizard
              definition={stage.definition}
              initialProgress={stage.progress}
              onSubmitted={() => setStage({ kind: "submitted" })}
              onConsentRequired={reload}
            />
          </>
        )}
      </Card>
    </div>
  );
}
