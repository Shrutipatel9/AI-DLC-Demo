import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { LogInForm } from "@/components/auth/login-form";
import { SecurityNotice } from "@/components/auth/security-notice";

export const metadata: Metadata = { title: "Log in · AI Facial Analysis" };

export default function LogInPage() {
  return (
    <AuthShell title="Log in">
      <SecurityNotice />
      <LogInForm />
    </AuthShell>
  );
}
