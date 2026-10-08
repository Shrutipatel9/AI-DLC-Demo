import type { Metadata } from "next";

import { ChangePasswordForm } from "@/components/settings/change-password-form";
import { SettingsPage } from "@/components/settings/settings-shell";

export const metadata: Metadata = { title: "Change password · AI Facial Analysis" };

// Settings -> Password (US11.5, WF-U2-8).
export default function ChangePasswordPage() {
  return (
    <SettingsPage current="/settings/password" title="Change password">
      <ChangePasswordForm />
    </SettingsPage>
  );
}
