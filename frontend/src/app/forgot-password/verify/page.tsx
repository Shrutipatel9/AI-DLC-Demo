import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { VerifyForm } from "@/components/auth/verify-form";

export const metadata: Metadata = { title: "Check your email · AI Facial Analysis" };

// Step 2 of the reset: the same code screen with purpose password_reset (WF-U2-7).
export default function ForgotPasswordVerifyPage() {
  return (
    <AuthShell title="Check your email">
      <VerifyForm />
    </AuthShell>
  );
}
