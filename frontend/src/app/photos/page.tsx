import type { Metadata } from "next";

import { AppShell } from "@/components/app/app-shell";
import { ProtectedRoute } from "@/components/app/protected-route";
import { PhotoFlow } from "@/components/photos/photo-flow";
import { STAGE } from "@/lib/journey";

export const metadata: Metadata = { title: "Photos · AI Facial Analysis" };

// Photo requirements, capture per angle and the same-person review (US5.1-US5.11). Its own
// route, so Next.js code-splits it.
export default function PhotosPage() {
  return (
    <ProtectedRoute stage={STAGE.photos}>
      <AppShell>
        <PhotoFlow />
      </AppShell>
    </ProtectedRoute>
  );
}
