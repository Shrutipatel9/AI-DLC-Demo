import type { Metadata } from "next";

import { AppShell } from "@/components/app/app-shell";
import { ProtectedRoute } from "@/components/app/protected-route";
import { VisualsScreen } from "@/components/visuals/visuals-screen";

export const metadata: Metadata = { title: "AI Visuals · AI Facial Analysis" };

// The AI Visuals screen (US9.2-US9.5). Its own route, so Next.js code-splits it.
export default function VisualsPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <VisualsScreen />
      </AppShell>
    </ProtectedRoute>
  );
}
