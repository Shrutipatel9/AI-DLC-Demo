import type { Metadata } from "next";

import { AppShell } from "@/components/app/app-shell";
import { JourneySteps } from "@/components/app/journey-steps";
import { ProtectedRoute } from "@/components/app/protected-route";
import { PaymentScreen } from "@/components/payments/payment-screen";
import { STAGE } from "@/lib/journey";

export const metadata: Metadata = { title: "Payment · FaceIQ" };

// The payment screen (US6.1, US6.2). Its own route, so Next.js code-splits it.
export default function PaymentPage() {
  return (
    <ProtectedRoute stage={STAGE.payment}>
      <AppShell>
        <JourneySteps current="payment" className="mx-auto max-w-[880px]" />
        <PaymentScreen />
      </AppShell>
    </ProtectedRoute>
  );
}
