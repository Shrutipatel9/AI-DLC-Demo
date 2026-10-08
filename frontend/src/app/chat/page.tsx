import type { Metadata } from "next";

import { AppShell } from "@/components/app/app-shell";
import { ProtectedRoute } from "@/components/app/protected-route";
import { Card } from "@/components/ui/card";

export const metadata: Metadata = { title: "Chat · AI Facial Analysis" };

// Placeholder until the Beauty Assistant (U9) arrives, so the header's Chat link has a page
// to open [Decided by delivery team].
export default function ChatPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <div className="mx-auto max-w-[900px]">
          <Card>
            <h1 className="text-2xl font-bold text-heading" data-testid="chat-placeholder">
              Chat is coming soon
            </h1>
            <p className="mt-2 text-base text-muted">
              Your Beauty Assistant will be here in a later update.
            </p>
          </Card>
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}
