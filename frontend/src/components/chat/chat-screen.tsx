"use client";

// The Beauty Assistant (US10.1, US10.3). Layout: a header, a scrolling conversation and the input
// bar underneath. The page height follows the visible viewport (`dvh`), so on a phone with the
// keyboard open the input and the latest reply stay on screen (AC10.1.6).
//
// - The conversation is a polite live region: a new reply is announced without moving focus
//   (AC10.1.3); the input keeps focus while the reply is awaited.
// - A message that got no reply stays on screen, marked, with an error toast (AC10.1.4).
// - At the daily limit the input is replaced by the time chat reopens (AC10.3.1).
import { MessageCircle, SendHorizontal, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { toast } from "@/components/feedback/toast";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { IconTile } from "@/components/ui/page-header";
import { useChat, type ShownMessage } from "@/lib/chat";

import {
  CHAT_INTRO,
  CHAT_TITLE,
  EMPTY_TEXT,
  EMPTY_TITLE,
  LIMIT_TOAST,
  LOAD_ERROR,
  NOT_ANSWERED,
  NO_REPORT_TEXT,
  NO_REPORT_TITLE,
  PENDING_TEXT,
  SEND_FAILURE,
  SUGGESTIONS,
  reopensText,
} from "./messages";

const MAX_LENGTH = 2000;

function Bubble({ message }: { message: ShownMessage }) {
  const mine = message.role === "user";
  return (
    <li
      className={`flex items-end gap-2.5 ${mine ? "flex-row-reverse" : ""}`}
      data-testid={`chat-message-${message.role}`}
    >
      {mine ? null : (
        <span
          aria-hidden="true"
          className="mb-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-gradient text-white"
        >
          <Sparkles className="size-4" />
        </span>
      )}
      <div className={`flex max-w-[85%] flex-col gap-1 ${mine ? "items-end" : "items-start"}`}>
        <p
          className={`whitespace-pre-wrap px-4 py-2.5 text-base shadow-sm ${
            mine
              ? "rounded-2xl rounded-br-md bg-accent-strong text-white"
              : "rounded-2xl rounded-bl-md border border-card-border bg-white text-heading"
          }`}
        >
          <span className="sr-only">{mine ? "You: " : "Assistant: "}</span>
          {message.text}
        </p>
        {message.failed ? (
          <span className="text-sm text-danger" data-testid="chat-message-failed">
            {NOT_ANSWERED}
          </span>
        ) : null}
      </div>
    </li>
  );
}

export function ChatScreen() {
  const chat = useChat();
  const [draft, setDraft] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [chat.messages.length, chat.sending, chat.phase]);

  // The on-screen keyboard changes the visible height: keep the latest reply in view (AC10.1.6).
  useEffect(() => {
    const keepLatestInView = () => end.current?.scrollIntoView?.({ block: "end" });
    window.addEventListener("resize", keepLatestInView);
    return () => window.removeEventListener("resize", keepLatestInView);
  }, []);

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || chat.sending) return;
    setDraft("");
    input.current?.focus(); // the Send button turns off while waiting; focus stays in the input
    const result = await chat.send(text);
    if (result === "failed") toast.error(SEND_FAILURE);
    if (result === "limit") {
      setDraft(text);
      toast.error(LIMIT_TOAST);
    }
    input.current?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  if (chat.phase === "loading") {
    return (
      <p role="status" className="text-base text-muted" data-testid="chat-loading">
        Loading your chat…
      </p>
    );
  }
  if (chat.phase === "error") {
    return (
      <div className="space-y-4" data-testid="chat-error">
        <p role="alert" className="text-base text-heading">
          {LOAD_ERROR}
        </p>
        <Button onClick={chat.reload} data-testid="chat-retry-button">
          Try again
        </Button>
      </div>
    );
  }
  if (chat.phase === "none") {
    return (
      <section className="space-y-4" data-testid="chat-none">
        <h1 className="text-2xl font-bold text-heading">{NO_REPORT_TITLE}</h1>
        <p className="text-base text-muted">{NO_REPORT_TEXT}</p>
        <Link href="/analysis" className={buttonVariants()} data-testid="chat-analysis-link">
          Go to your analysis
        </Link>
      </section>
    );
  }

  const limited = chat.remaining <= 0;
  return (
    <div
      className="mx-auto flex h-[calc(100dvh-9rem)] min-h-[12rem] max-w-[900px] flex-col gap-3"
      data-testid="chat"
    >
      <header className="flex items-center gap-3 [@media(max-height:520px)]:sr-only">
        <IconTile icon={MessageCircle} tone="violet" />
        <div>
          <h1 className="text-2xl font-bold text-heading">{CHAT_TITLE}</h1>
          <p className="text-sm text-subheading">{CHAT_INTRO}</p>
        </div>
      </header>

      <Card className="flex min-h-0 flex-1 flex-col overflow-hidden p-0 sm:p-0">
        <div
          className="min-h-0 flex-1 overflow-y-auto bg-surface-muted/40 p-4 sm:p-6"
          tabIndex={0}
          role="region"
          aria-label="Chat messages"
          data-testid="chat-scroll"
        >
          {chat.messages.length === 0 ? (
            <section
              className="mx-auto max-w-xl space-y-3 py-6 text-center"
              data-testid="chat-empty"
            >
              <span
                aria-hidden="true"
                className="mx-auto inline-flex size-14 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-raised"
              >
                <Sparkles className="size-7" />
              </span>
              <h2 className="text-xl font-bold text-heading">{EMPTY_TITLE}</h2>
              <p className="text-base text-subheading">{EMPTY_TEXT}</p>
              <ul className="flex flex-wrap justify-center gap-2 pt-2">
                {SUGGESTIONS.map((suggestion, index) => (
                  <li key={suggestion}>
                    <Button
                      type="button"
                      variant="secondary"
                      className="rounded-full"
                      onClick={() => {
                        setDraft(suggestion);
                        input.current?.focus();
                      }}
                      data-testid={`chat-suggestion-${index}`}
                    >
                      {suggestion}
                    </Button>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          <div
            role="log"
            aria-live="polite"
            aria-relevant="additions"
            aria-label="Conversation"
            data-testid="chat-log"
          >
            <ul className="space-y-3">
              {chat.messages.map((message) => (
                <Bubble key={message.key} message={message} />
              ))}
              {chat.sending ? (
                <li
                  className="flex items-center gap-2 text-sm text-muted"
                  data-testid="chat-pending"
                >
                  {PENDING_TEXT}
                </li>
              ) : null}
            </ul>
          </div>
          <div ref={end} />
        </div>

        <div className="border-t border-card-border bg-white p-3">
          {limited ? (
            <p role="status" className="text-base text-heading" data-testid="chat-limit">
              You&apos;ve reached today&apos;s chat limit. {reopensText(chat.resetsAt)}
            </p>
          ) : (
            <form onSubmit={(event) => void submit(event)} className="flex items-end gap-2">
              <label htmlFor="chat-input" className="sr-only">
                Your message
              </label>
              <textarea
                id="chat-input"
                ref={input}
                rows={2}
                maxLength={MAX_LENGTH}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Ask about your report"
                className="min-h-11 flex-1 resize-none rounded-ui border border-input-border bg-white px-3.5 py-2.5 text-base text-heading shadow-sm focus:border-accent-strong focus:shadow-focus focus:outline-none [@media(max-height:520px)]:h-11"
                data-testid="chat-input"
              />
              <Button
                type="submit"
                disabled={chat.sending || draft.trim() === ""}
                data-testid="chat-send-button"
              >
                <SendHorizontal aria-hidden="true" />
                Send
              </Button>
            </form>
          )}
          <p className="mt-1 text-sm text-muted" data-testid="chat-remaining">
            {chat.remaining} {chat.remaining === 1 ? "message" : "messages"} left today
          </p>
        </div>
      </Card>
    </div>
  );
}
