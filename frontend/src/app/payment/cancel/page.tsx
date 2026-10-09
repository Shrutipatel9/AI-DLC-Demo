import type { Metadata } from "next";

import { AppShell } from "@/components/app/app-shell";
import { JourneySteps } from "@/components/app/journey-steps";
import { ProtectedRoute } from "@/components/app/protected-route";
import { PaymentScreen } from "@/components/payments/payment-screen";

export const metadata: Metadata = { title: "Payment · FaceIQ" };

// Where Checkout sends the user after cancelling: the payment screen again, saying nothing was
// charged (AC6.2.3).
export default function PaymentCancelPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <JourneySteps current="payment" className="mx-auto max-w-[880px]" />
        <PaymentScreen cancelled />
      </AppShell>
    </ProtectedRoute>
  );
}
