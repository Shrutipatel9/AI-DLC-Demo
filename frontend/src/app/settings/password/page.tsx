import type { Metadata } from "next";

import { AppShell } from "@/components/app/app-shell";
import { ProtectedRoute } from "@/components/app/protected-route";
import { Card } from "@/components/ui/card";
import { ChangePasswordForm } from "@/components/settings/change-password-form";

export const metadata: Metadata = { title: "Change password · AI Facial Analysis" };

// Settings -> Password (US11.5, WF-U2-8). U10 adds the rest of Settings later.
export default function ChangePasswordPage() {
  return (
    <ProtectedRoute>
      <AppShell>
        <div className="mx-auto max-w-[480px]">
          <Card>
            <h1 className="mb-6 text-2xl font-bold text-heading">Change password</h1>
            <ChangePasswordForm />
          </Card>
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}
