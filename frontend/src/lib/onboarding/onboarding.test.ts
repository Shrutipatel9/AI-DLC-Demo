// Onboarding lib: the API calls go through the single client, the home status, and the pure
// wizard helpers (FE-004; US4.2).
import { beforeEach, describe, expect, it } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { errorResponse, jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { TEST_DEFINITION } from "@/test-utils/onboarding-server";

import {
  emptyValue,
  followUpVisible,
  isAnswered,
  loadOnboardingStatus,
  resumeIndex,
  saveAnswer,
  valueToSave,
  type Question,
} from "./index";

const consent = (given: boolean) => ({
  consentTextVersion: "consent-v1",
  consentText: "t",
  agreementText: "a",
  given,
});
const progress = (answers: Record<string, unknown>, submitted = false) => ({
  answers,
  visibleQuestionIds: [],
  submitted,
});

function question(id: string): Question {
  const found = TEST_DEFINITION.questions.find((q) => q.id === id);
  if (!found) throw new Error(id);
  return found;
}

describe("loadOnboardingStatus", () => {
  beforeEach(() => configureApiOrigin("http://api.test"));

  it("is not started without consent, and never asks for the response", async () => {
    const requests = mockFetch(
      route("GET", "/onboarding/consent", () => jsonResponse(200, consent(false))),
    );
    expect(await loadOnboardingStatus()).toBe("not_started");
    expect(requests).toHaveLength(1);
    expect(requests[0].headers["x-requested-with"]).toBe("XMLHttpRequest");
  });

  it("follows the saved response: not started, in progress, submitted", async () => {
    let body = progress({});
    mockFetch(
      route("GET", "/onboarding/consent", () => jsonResponse(200, consent(true))),
      route("GET", "/onboarding/response", () => jsonResponse(200, body)),
    );
    expect(await loadOnboardingStatus()).toBe("not_started");
    body = progress({ q1: { value: "x" } });
    expect(await loadOnboardingStatus()).toBe("in_progress");
    body = progress({ q1: { value: "x" } }, true);
    expect(await loadOnboardingStatus()).toBe("submitted");
  });

  it("treats a consent refusal as not started and passes other errors on", async () => {
    let code = "CONSENT_REQUIRED";
    mockFetch(
      route("GET", "/onboarding/consent", () => jsonResponse(200, consent(true))),
      route("GET", "/onboarding/response", () =>
        errorResponse(code === "CONSENT_REQUIRED" ? 403 : 500, code),
      ),
    );
    expect(await loadOnboardingStatus()).toBe("not_started");
    code = "INTERNAL_ERROR";
    await expect(loadOnboardingStatus()).rejects.toMatchObject({ code: "INTERNAL_ERROR" });
  });

  it("saveAnswer PUTs the value and follow-up to the encoded question path", async () => {
    const requests = mockFetch(() => jsonResponse(200, progress({})));
    await saveAnswer("q9", true, "Ibuprofen");
    expect(requests[0].method).toBe("PUT");
    expect(requests[0].url).toBe("http://api.test/onboarding/response/answers/q9");
    expect(requests[0].body).toEqual({ value: true, followUpText: "Ibuprofen" });
  });
});

describe("wizard helpers", () => {
  it("follow-ups open only on their trigger", () => {
    expect(followUpVisible(question("q9"), true)).toBe(true);
    expect(followUpVisible(question("q9"), false)).toBe(false);
    expect(followUpVisible(question("q9"), null)).toBe(false);
    expect(followUpVisible(question("q1"), "x")).toBe(false);
  });

  it("required questions need a non-empty answer; optional ones do not", () => {
    expect(isAnswered(question("q1"), null)).toBe(false);
    expect(isAnswered(question("q1"), "  ")).toBe(false);
    expect(isAnswered(question("q1"), "Pilot")).toBe(true);
    expect(isAnswered(question("q23"), "")).toBe(true);
    expect(isAnswered(question("q7"), [])).toBe(true);
    expect(isAnswered(question("q9"), false)).toBe(true);
  });

  it("values to save are trimmed and optional blanks become empty values", () => {
    expect(valueToSave(question("q1"), " Pilot ")).toBe("Pilot");
    expect(valueToSave(question("q1"), null)).toBeNull();
    expect(valueToSave(question("q7"), null)).toEqual([]);
    expect(valueToSave(question("q23"), null)).toBe("");
    expect(valueToSave(question("q9"), true)).toBe(true);
    expect(emptyValue(question("q7"))).toEqual([]);
    expect(emptyValue(question("q1"))).toBe("");
    expect(emptyValue(question("q9"))).toBeNull();
  });

  it("resumes at the first unanswered visible question, or the last one", () => {
    expect(resumeIndex(["q1", "q4", "q9"], { q1: {} })).toBe(1);
    expect(resumeIndex(["q1", "q4"], { q1: {}, q4: {} })).toBe(1);
    expect(resumeIndex([], {})).toBe(0);
  });
});
