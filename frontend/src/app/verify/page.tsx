import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { VerifyForm } from "@/components/auth/verify-form";

export const metadata: Metadata = { title: "Check your email · AI Facial Analysis" };

export default function VerifyPage() {
  return (
    <AuthShell title="Check your email">
      <VerifyForm />
    </AuthShell>
  );
}
