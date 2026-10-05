// Onboarding flow: consent, wizard navigation and branching, question types, disclaimer and
// submit, resume (US4.1-US4.4; AC4.1.1-AC4.1.2, AC4.2.1-AC4.2.6, AC4.3.1-AC4.3.4).
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { errorResponse, mockFetch, type RecordedRequest } from "@/test-utils/fetch-mock";
import { resetNextMocks, router, toastMock } from "@/test-utils/next-mocks";
import {
  DISCLAIMER,
  TEST_DEFINITION,
  newState,
  onboardingServer,
  type OnboardingServerState,
} from "@/test-utils/onboarding-server";

import { OnboardingFlow } from "./onboarding-flow";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

function start(state: OnboardingServerState, ...extra: Parameters<typeof mockFetch>) {
  const requests = mockFetch(...extra, onboardingServer(state));
  render(<OnboardingFlow />);
  return requests;
}

function puts(requests: RecordedRequest[]) {
  return requests.filter((r) => r.method === "PUT").map((r) => [r.url.split("/").at(-1), r.body]);
}

async function next(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByTestId("wizard-next-button"));
}

async function expectPosition(text: string) {
  expect(await screen.findByTestId("wizard-position")).toHaveTextContent(text);
}

const consented = () => newState({ consentGiven: true });

describe("Consent (US4.1)", () => {
  beforeEach(() => {
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("shows the configured text and keeps Continue disabled with the reason until ticked", async () => {
    start(newState());
    expect(await screen.findByTestId("consent-step")).toHaveTextContent(
      "Health answers never go to the AI service.",
    );
    expect(screen.getByTestId("onboarding-step")).toHaveTextContent("Step 1 of 5 · Consent");
    expect(screen.getByTestId("consent-continue-button")).toBeDisabled();
    expect(screen.getByTestId("consent-reason")).toHaveTextContent("Tick the box to continue.");
    expect(screen.queryByTestId("questionnaire-wizard")).toBeNull();
  });

  it("stores consent with the text version, confirms it and opens the questionnaire", async () => {
    const state = newState();
    const requests = start(state);
    const user = userEvent.setup();
    await user.click(await screen.findByTestId("consent-checkbox"));
    expect(screen.queryByTestId("consent-reason")).toBeNull();
    await user.click(screen.getByTestId("consent-continue-button"));
    await expectPosition("Question 1 of 5");
    const post = requests.find((r) => r.method === "POST");
    expect(post?.body).toEqual({ consentTextVersion: "consent-v1" });
    expect(toastMock.success).toHaveBeenCalledWith("Thank you. Your consent is saved.");
    expect(state.consentGiven).toBe(true);
  });

  it("reloads the text when it changed in the meantime", async () => {
    const state = newState();
    start(state);
    const user = userEvent.setup();
    await user.click(await screen.findByTestId("consent-checkbox"));
    state.consentVersion = "consent-v2";
    await user.click(screen.getByTestId("consent-continue-button"));
    await waitFor(() =>
      expect(toastMock.error).toHaveBeenCalledWith(
        "The consent text has changed. Please read it again.",
      ),
    );
    await waitFor(() => expect(screen.getByTestId("consent-checkbox")).not.toBeChecked());
    expect(screen.getByTestId("consent-continue-button")).toBeDisabled();
  });

  it("goes back to consent when the server refuses a save for missing consent", async () => {
    const state = consented();
    start(state);
    const user = userEvent.setup();
    await user.type(await screen.findByTestId("question-text-input"), "Designer");
    state.consentGiven = false;
    await next(user);
    expect(await screen.findByTestId("consent-step")).toBeInTheDocument();
  });
});

describe("Wizard navigation and branching (US4.2)", () => {
  beforeEach(() => {
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("starts at question 1 of the visible questions with an accessible progress bar", async () => {
    start(consented());
    await expectPosition("Question 1 of 5");
    const bar = screen.getByTestId("wizard-progress");
    expect(bar).toHaveAttribute("role", "progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "1");
    expect(bar).toHaveAttribute("aria-valuemax", "5");
    expect(screen.getByTestId("wizard-back-button")).toBeDisabled();
    expect(screen.getByTestId("onboarding-step")).toHaveTextContent("Questionnaire");
  });

  it("asks for an answer before Next and sends nothing", async () => {
    const requests = start(consented());
    const user = userEvent.setup();
    await screen.findByTestId("question-step");
    await next(user);
    expect(screen.getByTestId("question-error")).toHaveTextContent("Please enter an answer.");
    expect(screen.getByTestId("question-text-input")).toHaveAttribute("aria-invalid", "true");
    expect(puts(requests)).toEqual([]);
  });

  it("saves each answer on Next and moves on, moving focus to the new question", async () => {
    const requests = start(consented());
    const user = userEvent.setup();
    await user.type(await screen.findByTestId("question-text-input"), "  Designer ");
    await next(user);
    await expectPosition("Question 2 of 5");
    expect(puts(requests)).toEqual([["q1", { value: "Designer", followUpText: null }]]);
    expect(screen.getByTestId("question-legend")).toHaveTextContent("masculine or more feminine");
    expect(screen.getByTestId("question-legend")).toHaveFocus();
  });

  it("shows Q19 after a triggering answer and the count follows (AC4.2.2)", async () => {
    start(consented());
    const user = userEvent.setup();
    await user.type(await screen.findByTestId("question-text-input"), "Designer");
    await next(user);
    await user.click(await screen.findByTestId("question-option-masculine"));
    await next(user);
    await expectPosition("Question 3 of 6");
    await next(user); // q7 is optional
    await user.click(await screen.findByTestId("question-no"));
    await next(user);
    await expectPosition("Question 5 of 6");
    expect(screen.getByTestId("question-legend")).toHaveTextContent("Can you grow a full beard?");
  });

  it("Back keeps answers editable and a non-triggering answer skips Q19 (AC4.2.3, AC4.2.5)", async () => {
    const state = consented();
    state.answers = {
      q1: { value: "Designer", followUpText: null },
      q4: { value: "masculine", followUpText: null },
    };
    start(state);
    const user = userEvent.setup();
    await expectPosition("Question 3 of 6");
    await user.click(screen.getByTestId("wizard-back-button"));
    await expectPosition("Question 2 of 6");
    expect(screen.getByTestId("question-option-masculine")).toBeChecked();
    await user.click(screen.getByTestId("question-option-feminine"));
    await next(user);
    await expectPosition("Question 3 of 5");
    expect(state.answers.q4.value).toBe("feminine");
  });

  it("keeps the answer on screen and reports a failed save in a toast", async () => {
    start(consented(), (request) =>
      request.method === "PUT" ? errorResponse(500, "INTERNAL_ERROR") : undefined,
    );
    const user = userEvent.setup();
    await user.type(await screen.findByTestId("question-text-input"), "Designer");
    await next(user);
    await waitFor(() => expect(toastMock.error).toHaveBeenCalled());
    expect(screen.getByTestId("question-text-input")).toHaveValue("Designer");
    await expectPosition("Question 1 of 5");
  });

  it("shows the server's validation refusal next to the question", async () => {
    start(consented(), (request) =>
      request.method === "PUT"
        ? errorResponse(422, "VALIDATION_FAILED", {
            details: [{ field: "value", reason: "TOO_LONG" }],
          })
        : undefined,
    );
    const user = userEvent.setup();
    await user.type(await screen.findByTestId("question-text-input"), "Designer");
    await next(user);
    expect(await screen.findByTestId("question-error")).toHaveTextContent(
      "Please check your answer and try again.",
    );
    expect(toastMock.error).toHaveBeenCalledWith("We couldn't save your answer. Please try again.");
  });
});

describe("Question types", () => {
  beforeEach(() => {
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  function at(questionId: string): OnboardingServerState {
    const state = consented();
    const order = ["q1", "q4", "q7", "q9", "q19", "q23"];
    for (const id of order.slice(0, order.indexOf(questionId))) {
      if (id === "q1") state.answers.q1 = { value: "Designer", followUpText: null };
      if (id === "q4") state.answers.q4 = { value: "feminine", followUpText: null };
      if (id === "q7") state.answers.q7 = { value: [], followUpText: null };
      if (id === "q9") state.answers.q9 = { value: false, followUpText: null };
    }
    return state;
  }

  it("free text shows its placeholder and a character count", async () => {
    start(at("q1"));
    const input = await screen.findByTestId("question-text-input");
    expect(input).toHaveAttribute("placeholder", "e.g. Entrepreneur");
    await userEvent.setup().type(input, "Pilot");
    expect(screen.getByText("5 / 500 characters")).toBeInTheDocument();
    expect(screen.getByLabelText("What is your occupation?")).toBe(input);
  });

  it("single choice is a radio group with one selection", async () => {
    start(at("q4"));
    const user = userEvent.setup();
    await user.click(await screen.findByTestId("question-option-masculine"));
    await user.click(screen.getByTestId("question-option-no_preference"));
    expect(screen.getByTestId("question-option-masculine")).not.toBeChecked();
    expect(screen.getByTestId("question-option-no_preference")).toBeChecked();
    await next(user);
    await waitFor(() => expect(screen.getByTestId("wizard-position")).toHaveTextContent("of 6"));
  });

  it("multi-select groups options under headings and saves the chosen list", async () => {
    const requests = start(at("q7"));
    const user = userEvent.setup();
    await screen.findByTestId("question-option-botox");
    expect(screen.getByRole("group", { name: "Non-invasive treatments" })).toBeInTheDocument();
    await user.click(screen.getByTestId("question-option-botox"));
    await user.click(screen.getByTestId("question-option-laser"));
    await user.click(screen.getByTestId("question-option-botox"));
    await next(user);
    await waitFor(() =>
      expect(puts(requests)).toEqual([["q7", { value: ["laser"], followUpText: null }]]),
    );
  });

  it("an optional multi-select can be skipped and is saved as an empty list", async () => {
    const requests = start(at("q7"));
    await screen.findByTestId("question-option-botox");
    expect(screen.getByText("Optional")).toBeInTheDocument();
    await next(userEvent.setup());
    await waitFor(() =>
      expect(puts(requests)).toEqual([["q7", { value: [], followUpText: null }]]),
    );
  });

  it("Yes reveals the follow-up, No hides it, and its text is saved (AC4.2.4)", async () => {
    const requests = start(at("q9"));
    const user = userEvent.setup();
    await user.click(await screen.findByTestId("question-yes"));
    const followUp = screen.getByTestId("question-follow-up-input");
    expect(screen.getByLabelText(/Please list your medications/)).toBe(followUp);
    await user.type(followUp, "Ibuprofen");
    await user.click(screen.getByTestId("question-no"));
    expect(screen.queryByTestId("question-follow-up")).toBeNull();
    await user.click(screen.getByTestId("question-yes"));
    expect(screen.getByTestId("question-follow-up-input")).toHaveValue("Ibuprofen");
    await next(user);
    await waitFor(() =>
      expect(puts(requests)).toEqual([["q9", { value: true, followUpText: "Ibuprofen" }]]),
    );
  });

  it("Yes/No asks for a choice before moving on", async () => {
    start(at("q9"));
    await screen.findByTestId("question-yes");
    await next(userEvent.setup());
    expect(screen.getByTestId("question-error")).toHaveTextContent("Please choose an answer.");
  });
});

describe("Disclaimer and submit (US4.3)", () => {
  beforeEach(() => {
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  function allButLast(): OnboardingServerState {
    const state = consented();
    state.answers = {
      q1: { value: "Designer", followUpText: null },
      q4: { value: "feminine", followUpText: null },
      q7: { value: [], followUpText: null },
      q9: { value: false, followUpText: null },
    };
    return state;
  }

  it("the last question shows the exact disclaimer; Submit is disabled with the reason", async () => {
    start(allButLast());
    await expectPosition("Question 5 of 5");
    expect(screen.getByTestId("disclaimer-text")).toHaveTextContent(DISCLAIMER);
    expect(screen.getByTestId("wizard-submit-button")).toBeDisabled();
    expect(screen.getByTestId("disclaimer-reason")).toHaveTextContent(
      "Please confirm the statement above to submit.",
    );
    expect(screen.queryByTestId("wizard-next-button")).toBeNull();
  });

  it("ticking and submitting saves the last answer, submits and confirms", async () => {
    const state = allButLast();
    const requests = start(state);
    const user = userEvent.setup();
    await user.type(await screen.findByTestId("question-text-input"), "Nothing else");
    await user.click(screen.getByTestId("disclaimer-checkbox"));
    expect(screen.queryByTestId("disclaimer-reason")).toBeNull();
    await user.click(screen.getByTestId("wizard-submit-button"));
    expect(await screen.findByTestId("onboarding-submitted")).toBeInTheDocument();
    expect(puts(requests).at(-1)).toEqual(["q23", { value: "Nothing else", followUpText: null }]);
    const submit = requests.find((r) => r.url.endsWith("/submit"));
    expect(submit?.body).toEqual({ disclaimerConfirmed: true });
    expect(toastMock.success).toHaveBeenCalledWith("Thank you. Your answers are submitted.");
    await user.click(screen.getByTestId("onboarding-home-button"));
    expect(router.push).toHaveBeenCalledWith("/home");
    await user.click(screen.getByTestId("onboarding-photos-button"));
    expect(router.push).toHaveBeenCalledWith("/photos");
  });

  it("'I can't confirm' opens the supportive message in place, focused, without an invented link", async () => {
    const requests = start(allButLast());
    const user = userEvent.setup();
    await user.click(await screen.findByTestId("disclaimer-cannot-confirm-link"));
    const panel = screen.getByTestId("support-panel");
    expect(within(panel).getByRole("heading")).toHaveFocus();
    expect(panel).toHaveTextContent("Your answers are saved.");
    expect(screen.queryByTestId("support-panel-link")).toBeNull();
    expect(requests.some((r) => r.url.endsWith("/submit"))).toBe(false);
    await user.click(screen.getByTestId("support-panel-back-button"));
    expect(screen.getByTestId("wizard-submit-button")).toBeDisabled();
  });

  it("shows the configured professional-support link", async () => {
    const state = allButLast();
    state.definition = { ...TEST_DEFINITION, supportUrl: "https://support.example.test/" };
    start(state);
    await userEvent.setup().click(await screen.findByTestId("disclaimer-cannot-confirm-link"));
    expect(screen.getByTestId("support-panel-link")).toHaveAttribute(
      "href",
      "https://support.example.test/",
    );
  });

  it("jumps to a required question the server reports as unanswered", async () => {
    const state = allButLast();
    state.answers.q1 = { value: "", followUpText: null };
    state.answers.q23 = { value: "", followUpText: null };
    start(state);
    const user = userEvent.setup();
    await user.click(await screen.findByTestId("disclaimer-checkbox"));
    await user.click(screen.getByTestId("wizard-submit-button"));
    await expectPosition("Question 1 of 5");
    expect(screen.getByTestId("question-error")).toHaveTextContent("Please choose an answer.");
    expect(toastMock.error).toHaveBeenCalledWith("Please answer every question before submitting.");
    expect(state.submitted).toBe(false);
  });
});

describe("Resume (AC4.2.6)", () => {
  beforeEach(() => {
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("resumes at the first unanswered question with earlier answers kept", async () => {
    const state = consented();
    state.answers = {
      q1: { value: "Designer", followUpText: null },
      q4: { value: "feminine", followUpText: null },
    };
    start(state);
    await expectPosition("Question 3 of 5");
    await userEvent.setup().click(screen.getByTestId("wizard-back-button"));
    expect(await screen.findByTestId("question-option-feminine")).toBeChecked();
  });

  it("an already submitted questionnaire shows the submitted state", async () => {
    start(newState({ consentGiven: true, submitted: true }));
    expect(await screen.findByTestId("onboarding-submitted")).toHaveTextContent(
      "Your questionnaire is submitted",
    );
  });

  it("a load failure is reported and can be retried", async () => {
    const state = consented();
    let fail = true;
    start(state, (request) =>
      fail && request.url.endsWith("/onboarding/questionnaire")
        ? errorResponse(503, "UPSTREAM_UNAVAILABLE")
        : undefined,
    );
    expect(await screen.findByTestId("onboarding-error")).toBeInTheDocument();
    expect(toastMock.error).toHaveBeenCalled();
    fail = false;
    await userEvent.setup().click(screen.getByTestId("onboarding-retry-button"));
    await expectPosition("Question 1 of 5");
  });
});
