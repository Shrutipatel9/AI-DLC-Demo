"use client";

// "Send a new code" with a countdown (US3.3, WF-U2-1; AC3.3.1, AC3.3.3; BR1.1, BR1.3). It is
// disabled until `resendAvailableAt` and becomes available by itself. During a lockout it
// says when to try again.
import { useEffect, useState } from "react";

import { toast } from "@/components/feedback/toast";
import { Button } from "@/components/ui/button";
import { isApiError } from "@/lib/api/errors";
import { useAuthActions } from "@/lib/auth";

import { messageFor } from "./messages";

function remainingSeconds(untilMs: number, nowMs: number): number {
  return Math.max(0, Math.ceil((untilMs - nowMs) / 1000));
}

function clock(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

export function ResendCodeButton({
  availableAt,
  onResent,
}: {
  availableAt: string;
  onResent: () => void;
}) {
  const { resendCode } = useAuthActions();
  const [now, setNow] = useState(() => Date.now());
  const [override, setOverride] = useState<{ until: number; locked: boolean } | null>(null);
  const [sending, setSending] = useState(false);
  const until = override?.until ?? Date.parse(availableAt);
  const seconds = remainingSeconds(until, now);

  useEffect(() => {
    if (seconds <= 0) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [seconds]);

  async function onClick() {
    setSending(true);
    try {
      await resendCode();
      setOverride(null);
      setNow(Date.now());
      onResent();
      toast.success("We sent a new code. Check your email.");
    } catch (error) {
      if (!isApiError(error)) throw error;
      const wait = (error.retryAfterSeconds ?? 60) * 1000;
      if (error.code === "CODE_RESEND_COOLDOWN" || error.code === "CODE_LOCKED") {
        setOverride({ until: Date.now() + wait, locked: error.code === "CODE_LOCKED" });
        setNow(Date.now());
      }
      toast.error(messageFor(error));
    } finally {
      setSending(false);
    }
  }

  const waiting = seconds > 0;
  let label = "Send a new code";
  if (waiting && override?.locked) label = `Try again in ${clock(seconds)}`;
  else if (waiting) label = `Send a new code in ${clock(seconds)}`;
  return (
    <Button
      type="button"
      variant="secondary"
      width="full"
      disabled={waiting || sending}
      onClick={() => void onClick()}
      data-testid="resend-code-button"
    >
      {sending ? "Sending…" : label}
    </Button>
  );
}
