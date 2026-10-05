import type { Metadata } from "next";

import { AppShell } from "@/components/app/app-shell";
import { ProtectedRoute } from "@/components/app/protected-route";
import { PaymentScreen } from "@/components/payments/payment-screen";

export const metadata: Metadata = { title: "Payment · AI Facial Analysis" };

// The payment screen (US6.1, US6.2). Its own route, so Next.js code-splits it.
export default function PaymentPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <PaymentScreen />
      </AppShell>
    </ProtectedRoute>
  );
}
