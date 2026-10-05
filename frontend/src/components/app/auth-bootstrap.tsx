"use client";

// Runs the session restore once per tab (WF-U2-2) and gives the session layer its toast and
// router (it may not import UI code itself). Renders nothing.
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { toast } from "@/components/feedback/toast";
import { useAuthActions } from "@/lib/auth";

export function AuthBootstrap() {
  const router = useRouter();
  const { restore, setSessionNotifier } = useAuthActions();

  useEffect(() => {
    setSessionNotifier({ error: toast.error, navigate: (path) => router.replace(path) });
  }, [router, setSessionNotifier]);

  useEffect(() => {
    void restore();
  }, [restore]);

  return null;
}
