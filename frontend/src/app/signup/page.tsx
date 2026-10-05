import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthShell } from "@/components/auth/auth-shell";
import { SignUpForm } from "@/components/auth/signup-form";

export const metadata: Metadata = { title: "Create your account · AI Facial Analysis" };

export default function SignUpPage() {
  return (
    <AuthShell title="Create your account">
      <Suspense>
        <SignUpForm />
      </Suspense>
    </AuthShell>
  );
}
