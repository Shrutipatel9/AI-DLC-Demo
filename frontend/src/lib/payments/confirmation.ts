// Waiting for the payment confirmation (US6.5; FR7.4). The server's status changes only when it
// receives the provider's verified webhook, never because the browser came back to the success
// page, so this hook polls GET /payments/status (contract: every 2-3 s) until it reads `paid`.
//
// - `phase` is "loading" until the first answer, then the server's state;
// - `waitedTooLong` turns true once the configured wait (`confirmWaitSeconds`, AC6.5.3) has
//   passed without a confirmation; polling continues, so a late confirmation still shows;
// - a failed poll is retried on the next tick (a payment is never assumed either way).
import { useEffect, useRef, useState } from "react";

import { getPaymentStatus, type PaymentState } from "./api";

export const POLL_INTERVAL_MS = 2_000;

export interface Confirmation {
  phase: "loading" | PaymentState;
  waitedTooLong: boolean;
}

export function usePaymentConfirmation(intervalMs: number = POLL_INTERVAL_MS): Confirmation {
  const [confirmation, setConfirmation] = useState<Confirmation>({
    phase: "loading",
    waitedTooLong: false,
  });
  const startedAt = useRef<number | null>(null);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    startedAt.current = Date.now();

    const poll = async () => {
      let paid = false;
      try {
        const status = await getPaymentStatus();
        if (!active) return;
        paid = status.state === "paid";
        const elapsedMs = Date.now() - (startedAt.current ?? Date.now());
        setConfirmation({
          phase: status.state,
          waitedTooLong: !paid && elapsedMs >= status.confirmWaitSeconds * 1000,
        });
      } catch {
        // Keep the last known state and try again on the next tick.
      }
      if (active && !paid) timer = setTimeout(() => void poll(), intervalMs);
    };
    void poll();

    return () => {
      active = false;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [intervalMs]);

  return confirmation;
}
