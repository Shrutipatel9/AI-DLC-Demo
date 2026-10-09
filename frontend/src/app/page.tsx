import type { Metadata } from "next";

import { LandingPage } from "@/components/landing/landing-page";

export const metadata: Metadata = { title: "FaceIQ — AI facial analysis" };

// The landing page (US2.1, US2.2).
export default function RootPage() {
  return <LandingPage />;
}
