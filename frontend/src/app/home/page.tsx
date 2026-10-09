import type { Metadata } from "next";

import { HomeView } from "@/components/app/home-view";
import { ProtectedRoute } from "@/components/app/protected-route";
import { STAGE } from "@/lib/journey";

export const metadata: Metadata = { title: "Home · FaceIQ" };

export default function HomePage() {
  return (
    <ProtectedRoute stage={STAGE.home}>
      <HomeView />
    </ProtectedRoute>
  );
}
