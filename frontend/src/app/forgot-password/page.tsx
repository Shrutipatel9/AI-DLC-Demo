import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";

export const metadata: Metadata = { title: "Reset your password · AI Facial Analysis" };

export default function ForgotPasswordPage() {
  return (
    <AuthShell title="Reset your password">
      <ForgotPasswordForm />
    </AuthShell>
  );
}
