// Beauty Assistant endpoints (U9; contract C1 /chat/messages). UI code never imports the API
// client (FE-004); it calls these functions through `@/lib/chat`.
import { apiRequest } from "@/lib/api/client";
import type { components } from "@/lib/api/types.gen";

export type ChatState = components["schemas"]["ChatStateOut"];
export type ChatReply = components["schemas"]["ChatReplyOut"];
export type ChatMessage = components["schemas"]["ChatMessageOut"];

/** The model can take a while: the contract gives chat 60 s (C1 §6). */
export const CHAT_TIMEOUT_MS = 60_000;

/** The conversation and today's remaining messages (402 before payment, 404 REPORT_NOT_READY). */
export function getChat(): Promise<ChatState> {
  return apiRequest<ChatState>("/chat/messages");
}

/** Send one message and get the whole reply (429 CHAT_DAILY_LIMIT_REACHED over the limit). */
export function sendChatMessage(text: string): Promise<ChatReply> {
  return apiRequest<ChatReply>("/chat/messages", {
    method: "POST",
    body: { text },
    timeoutMs: CHAT_TIMEOUT_MS,
  });
}
