// Chat screen wording (US10.1, US10.3).
export const CHAT_TITLE = "Beauty Assistant";
export const CHAT_INTRO =
  "Ask about your own report. The assistant gives cosmetic commentary only and does not answer medical or medication questions.";
export const EMPTY_TITLE = "Ask me about your report";
export const EMPTY_TEXT =
  "I can explain your scores and measurements, what each feature section means and how to read your recommendations. Try one of these, or type your own question.";
export const SUGGESTIONS = [
  "What does my symmetry score mean?",
  "Which features should I focus on first?",
  "Can you explain my recommendations in simple words?",
] as const;
export const PENDING_TEXT = "Your reply is on its way…";
export const SEND_FAILURE =
  "The assistant couldn't answer. Your message is kept; please try again.";
export const LIMIT_TOAST = "You've reached today's chat limit.";
export const NOT_ANSWERED = "Not answered. Send it again to get a reply.";
export const LOAD_ERROR = "We couldn't load your chat. Please try again.";
export const NO_REPORT_TITLE = "Chat opens after your analysis";
export const NO_REPORT_TEXT = "Once your report is ready, you can ask the assistant about it here.";

/** "Chat reopens Friday at 12:00 AM" in the person's own time zone. */
export function reopensText(resetsAt: string | null): string {
  if (!resetsAt) return "Chat reopens tomorrow.";
  const when = new Date(resetsAt);
  if (Number.isNaN(when.getTime())) return "Chat reopens tomorrow.";
  const text = when.toLocaleString(undefined, {
    weekday: "long",
    hour: "numeric",
    minute: "2-digit",
  });
  return `Chat reopens ${text}.`;
}
