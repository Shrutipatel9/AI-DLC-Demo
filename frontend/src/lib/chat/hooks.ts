// The chat conversation (US10.1, US10.3).
//
// - `phase` is "loading" until the first answer, "none" when there is no report to talk about
//   (402 before payment, 404 REPORT_NOT_READY), "error" for anything else, then "ready".
// - `send` shows the user's message at once. A failed call keeps it on screen, marked
//   `failed`, so nothing the person typed is lost (AC10.1.4). Over the daily limit the message
//   is taken back out, because the server did not keep it, and the reopening time is shown.
import { useCallback, useEffect, useRef, useState } from "react";

import { isApiError } from "@/lib/api/errors";

import { getChat, sendChatMessage } from "./api";

export type LoadPhase = "loading" | "none" | "error" | "ready";

export interface ShownMessage {
  key: string;
  role: "user" | "assistant";
  text: string;
  /** The assistant did not answer this message (kept so it is not lost). */
  failed: boolean;
}

export type SendResult = "ok" | "failed" | "limit";

export interface Chat {
  phase: LoadPhase;
  messages: ShownMessage[];
  /** Replies left today (0 = the daily limit is reached). */
  remaining: number;
  /** When chat reopens (next 00:00 UTC), an ISO date-time. */
  resetsAt: string | null;
  /** A message is waiting for its reply. */
  sending: boolean;
  send: (text: string) => Promise<SendResult>;
  reload: () => void;
}

export function useChat(): Chat {
  const [phase, setPhase] = useState<LoadPhase>("loading");
  const [messages, setMessages] = useState<ShownMessage[]>([]);
  const [remaining, setRemaining] = useState(0);
  const [resetsAt, setResetsAt] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [generation, setGeneration] = useState(0);
  const counter = useRef(0);

  useEffect(() => {
    let active = true;
    getChat()
      .then((state) => {
        if (!active) return;
        // A user message that has no reply after it was never answered.
        setMessages(
          state.messages.map((message, index, all) => ({
            key: `stored-${index}`,
            role: message.role,
            text: message.text,
            failed: message.role === "user" && all[index + 1]?.role !== "assistant",
          })),
        );
        setRemaining(state.remainingToday);
        setResetsAt(state.resetsAt);
        setPhase("ready");
      })
      .catch((error: unknown) => {
        if (!active) return;
        const missing =
          isApiError(error) &&
          (error.code === "REPORT_NOT_READY" || error.code === "PAYMENT_REQUIRED");
        setPhase(missing ? "none" : "error");
      });
    return () => {
      active = false;
    };
  }, [generation]);

  const reload = useCallback(() => {
    setPhase("loading");
    setGeneration((value) => value + 1);
  }, []);

  const send = useCallback(async (text: string): Promise<SendResult> => {
    counter.current += 1;
    const key = `sent-${counter.current}`;
    setMessages((current) => [...current, { key, role: "user", text, failed: false }]);
    setSending(true);
    try {
      const reply = await sendChatMessage(text);
      setMessages((current) => [
        ...current,
        { key: `${key}-reply`, role: "assistant", text: reply.reply, failed: false },
      ]);
      setRemaining(reply.remainingToday);
      setResetsAt(reply.resetsAt);
      return "ok";
    } catch (error) {
      if (isApiError(error) && error.code === "CHAT_DAILY_LIMIT_REACHED") {
        const detail = error.details.find((item) => typeof item.resetsAt === "string");
        setMessages((current) => current.filter((message) => message.key !== key));
        setRemaining(0);
        if (detail) setResetsAt(detail.resetsAt as string);
        return "limit";
      }
      setMessages((current) =>
        current.map((message) => (message.key === key ? { ...message, failed: true } : message)),
      );
      return "failed";
    } finally {
      setSending(false);
    }
  }, []);

  return { phase, messages, remaining, resetsAt, sending, send, reload };
}
