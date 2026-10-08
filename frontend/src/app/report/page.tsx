import type { Metadata } from "next";

import { AppShell } from "@/components/app/app-shell";
import { ProtectedRoute } from "@/components/app/protected-route";
import { ReportScreen } from "@/components/report/report-screen";

export const metadata: Metadata = { title: "Your report · AI Facial Analysis" };

// The report (US8.3-US8.8). Its own route, so Next.js code-splits it.
export default function ReportPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <ReportScreen />
      </AppShell>
    </ProtectedRoute>
  );
}
