import type { Metadata } from "next";

import { AppShell } from "@/components/app/app-shell";
import { JourneySteps } from "@/components/app/journey-steps";
import { ProtectedRoute } from "@/components/app/protected-route";
import { OnboardingFlow } from "@/components/onboarding/onboarding-flow";
import { STAGE } from "@/lib/journey";

export const metadata: Metadata = { title: "Questionnaire · FaceIQ" };

// Consent and questionnaire (US4.1-US4.4). Its own route, so Next.js code-splits it.
export default function OnboardingPage() {
  return (
    <ProtectedRoute stage={STAGE.onboarding}>
      <AppShell>
        <JourneySteps current="questionnaire" className="mx-auto max-w-[880px]" />
        <OnboardingFlow />
      </AppShell>
    </ProtectedRoute>
  );
}
