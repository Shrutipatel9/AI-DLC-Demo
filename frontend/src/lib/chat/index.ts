// The only chat entry point for UI code (FE-004: UI never imports the API client).
export { getChat, sendChatMessage, type ChatMessage, type ChatReply, type ChatState } from "./api";
export { useChat, type Chat, type LoadPhase, type SendResult, type ShownMessage } from "./hooks";
