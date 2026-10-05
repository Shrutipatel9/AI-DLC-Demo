import type { Metadata } from "next";

import { AppShell } from "@/components/app/app-shell";
import { ProtectedRoute } from "@/components/app/protected-route";
import { PaymentScreen } from "@/components/payments/payment-screen";

export const metadata: Metadata = { title: "Payment · AI Facial Analysis" };

// Where Checkout sends the user after cancelling: the payment screen again, saying nothing was
// charged (AC6.2.3).
export default function PaymentCancelPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <PaymentScreen cancelled />
      </AppShell>
    </ProtectedRoute>
  );
}
