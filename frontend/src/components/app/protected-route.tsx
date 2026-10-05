"use client";

// Guards signed-in pages (BR6.1): waits while the session is restored, sends a signed-out
// visitor to /login, and renders the page once signed in.
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth, useAuthActions } from "@/lib/auth";

import { FullPageLoader } from "./full-page-loader";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { status, restoreFailed } = useAuth();
  const { restore } = useAuthActions();

  useEffect(() => {
    if (status === "signedOut") router.replace("/login");
  }, [status, router]);

  if (status !== "signedIn") {
    return <FullPageLoader failed={restoreFailed} onRetry={() => void restore()} />;
  }
  return <>{children}</>;
}
