import type { Metadata } from "next";

import { AnalysisProgress } from "@/components/analysis/analysis-progress";
import { AppShell } from "@/components/app/app-shell";
import { ProtectedRoute } from "@/components/app/protected-route";
import { STAGE } from "@/lib/journey";

export const metadata: Metadata = { title: "Your analysis · AI Facial Analysis" };

// The analysis progress screen (US7.2, US7.11). Its own route, so Next.js code-splits it.
export default function AnalysisPage() {
  return (
    <ProtectedRoute stage={STAGE.analysis}>
      <AppShell>
        <AnalysisProgress />
      </AppShell>
    </ProtectedRoute>
  );
}
