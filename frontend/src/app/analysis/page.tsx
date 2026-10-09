import type { Metadata } from "next";

import { AnalysisProgress } from "@/components/analysis/analysis-progress";
import { AppShell } from "@/components/app/app-shell";
import { JourneySteps } from "@/components/app/journey-steps";
import { ProtectedRoute } from "@/components/app/protected-route";
import { STAGE } from "@/lib/journey";

export const metadata: Metadata = { title: "Your analysis · FaceIQ" };

// The analysis progress screen (US7.2, US7.11). Its own route, so Next.js code-splits it.
export default function AnalysisPage() {
  return (
    <ProtectedRoute stage={STAGE.analysis}>
      <AppShell>
        <JourneySteps current="analysis" className="mx-auto max-w-[880px]" />
        <AnalysisProgress />
      </AppShell>
    </ProtectedRoute>
  );
}
