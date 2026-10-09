import type { Metadata } from "next";

import { AppShell } from "@/components/app/app-shell";
import { JourneySteps } from "@/components/app/journey-steps";
import { ProtectedRoute } from "@/components/app/protected-route";
import { PaymentConfirmation } from "@/components/payments/payment-confirmation";
import { STAGE } from "@/lib/journey";

export const metadata: Metadata = { title: "Confirming payment · FaceIQ" };

// Where Checkout sends the user after paying: "confirming your payment" until the server has
// the verified webhook (US6.5). The redirect itself is never trusted (FR7.4).
export default function PaymentSuccessPage() {
  return (
    <ProtectedRoute stage={STAGE.confirming}>
      <AppShell>
        <JourneySteps current="payment" className="mx-auto max-w-[880px]" />
        <PaymentConfirmation />
      </AppShell>
    </ProtectedRoute>
  );
}
