import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { ResetPasswordForm } from "@/components/auth/reset-password-form";

export const metadata: Metadata = { title: "Choose a new password · AI Facial Analysis" };

export default function ResetPasswordPage() {
  return (
    <AuthShell title="Choose a new password">
      <ResetPasswordForm />
    </AuthShell>
  );
}
