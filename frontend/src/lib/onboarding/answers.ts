// Pure helpers for the questionnaire wizard: follow-up visibility, local "is answered"
// checks (the server re-validates everything, D3) and the next/previous visible question.
import type { AnswerValue, Question } from "./api";

/** A draft answer on screen: the value (or null when nothing is chosen) and follow-up text. */
export interface DraftAnswer {
  value: AnswerValue | null;
  followUpText: string;
}

/** Whether the question's follow-up field is revealed by `value` (AC4.2.4). */
export function followUpVisible(question: Question, value: AnswerValue | null): boolean {
  return question.followUp != null && value !== null && value === question.followUp.showWhen;
}

/** Whether a draft can be saved. Required questions need a non-empty answer. */
export function isAnswered(question: Question, value: AnswerValue | null): boolean {
  if (value === null) return false;
  if (typeof value === "string") return value.trim().length > 0 || !question.required;
  if (Array.isArray(value)) return value.length > 0 || !question.required;
  return true;
}

/** The value to send: optional empty answers are sent as empty text or an empty list. */
export function valueToSave(question: Question, value: AnswerValue | null): AnswerValue | null {
  if (value !== null) return typeof value === "string" ? value.trim() : value;
  if (question.required) return null;
  if (question.type === "multi") return [];
  if (question.type === "text") return "";
  return null;
}

/** The empty draft for a question type. */
export function emptyValue(question: Question): AnswerValue | null {
  if (question.type === "multi") return [];
  if (question.type === "text") return "";
  return null;
}

/** The first visible question that has no saved answer (resume point, AC4.2.6). */
export function resumeIndex(visibleIds: string[], answered: Record<string, unknown>): number {
  const index = visibleIds.findIndex((id) => !(id in answered));
  return index === -1 ? Math.max(visibleIds.length - 1, 0) : index;
}
