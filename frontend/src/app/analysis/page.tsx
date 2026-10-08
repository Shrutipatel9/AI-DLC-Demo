import type { Metadata } from "next";

import { AnalysisProgress } from "@/components/analysis/analysis-progress";
import { AppShell } from "@/components/app/app-shell";
import { ProtectedRoute } from "@/components/app/protected-route";

export const metadata: Metadata = { title: "Your analysis · AI Facial Analysis" };

// The analysis progress screen (US7.2, US7.11). Its own route, so Next.js code-splits it.
export default function AnalysisPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <AnalysisProgress />
      </AppShell>
    </ProtectedRoute>
  );
}
