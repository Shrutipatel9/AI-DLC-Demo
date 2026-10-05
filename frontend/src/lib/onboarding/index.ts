// The only onboarding entry point for UI code (FE-004: UI never imports the API client).
export {
  getConsent,
  getProgress,
  getQuestionnaire,
  giveConsent,
  loadOnboardingStatus,
  saveAnswer,
  submitQuestionnaire,
  type AnswerValue,
  type ConsentState,
  type OnboardingStatus,
  type Question,
  type QuestionnaireDefinition,
  type QuestionnaireProgress,
  type SavedAnswer,
} from "./api";
export {
  emptyValue,
  followUpVisible,
  isAnswered,
  resumeIndex,
  valueToSave,
  type DraftAnswer,
} from "./answers";
