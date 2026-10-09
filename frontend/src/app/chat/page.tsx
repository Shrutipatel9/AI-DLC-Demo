import type { Metadata } from "next";

import { AppShell } from "@/components/app/app-shell";
import { ProtectedRoute } from "@/components/app/protected-route";
import { ChatScreen } from "@/components/chat/chat-screen";
import { STAGE } from "@/lib/journey";

export const metadata: Metadata = { title: "Chat · FaceIQ" };

// The Beauty Assistant (US10.1-US10.3). Its own route, so Next.js code-splits it.
export default function ChatPage() {
  return (
    <ProtectedRoute stage={STAGE.home}>
      <AppShell>
        <ChatScreen />
      </AppShell>
    </ProtectedRoute>
  );
}
