// U3 onboarding journey (US4.1-US4.4; NFR9.6, NFR9.7). Runs against the production web build
// and a running API with the real [QS] seed definition; codes come from Mailpit.
// The scenario tagged @checkpoint is part of the checkpoint subset (desktop only) in
// scripts/verify-skeleton.sh; CI and scripts/verify.sh run every scenario at both viewports.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const MAILPIT_URL = process.env.MAILPIT_URL ?? "http://127.0.0.1:8025";
const PASSWORD = "Sunrise2026x";
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const DISCLAIMER_START = "I hereby confirm that I do not have any concerns";

interface MailpitSummary {
  ID: string;
  Created: string;
}

async function latestCode(page: Page, email: string, subject: string, after: number) {
  let code: string | null = null;
  await expect
    .poll(
      async () => {
        const search = await page.request.get(`${MAILPIT_URL}/api/v1/search`, {
          params: { query: `to:"${email}" subject:"${subject}"` },
        });
        if (!search.ok()) return null;
        const { messages } = (await search.json()) as { messages: MailpitSummary[] };
        const fresh = messages
          .filter((message) => new Date(message.Created).getTime() >= after - 2_000)
          .sort((a, b) => b.Created.localeCompare(a.Created));
        if (fresh.length === 0) return null;
        const detail = await page.request.get(`${MAILPIT_URL}/api/v1/message/${fresh[0].ID}`);
        const { Text } = (await detail.json()) as { Text: string };
        code = /\b(\d{6})\b/.exec(Text)?.[1] ?? null;
        return code;
      },
      { timeout: 20_000, message: `no "${subject}" email for ${email}` },
    )
    .not.toBeNull();
  return code as unknown as string;
}

async function expectAccessible(page: Page, screen: string) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, `axe violations on ${screen}`).toEqual([]);
}

async function signUp(page: Page, label: string): Promise<void> {
  const email = `e2e-onb-${label}-${Date.now()}-${test.info().project.name}@example.test`;
  await page.goto("/signup");
  await page.getByTestId("signup-fullname-input").fill("Maya Onboarding");
  await page.getByTestId("signup-email-input").fill(email);
  await page.getByTestId("signup-password-input").fill(PASSWORD);
  const sentAt = Date.now();
  await page.getByTestId("signup-submit-button").click();
  await expect(page).toHaveURL(/\/verify$/);
  await page
    .getByTestId("verify-code-input")
    .fill(await latestCode(page, email, "Your sign-up code", sentAt));
  await page.getByTestId("verify-submit-button").click();
  await expect(page.getByTestId("home-greeting")).toHaveText("Hi, Maya Onboarding");
}

async function consent(page: Page) {
  await expect(page.getByTestId("home-onboarding-link")).toHaveText("Start your questionnaire");
  await page.getByTestId("home-onboarding-link").click();
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByTestId("consent-continue-button")).toBeDisabled();
  await page.getByTestId("consent-checkbox").check();
  await page.getByTestId("consent-continue-button").click();
  await expect(page.getByTestId("wizard-position")).toHaveText("Question 1 of 22");
}

/** Answer the current question: Q4 with `q4`, Q9 "Yes" with a follow-up, other Yes/No "No". */
async function answerCurrent(page: Page, q4: string) {
  const legend = (await page.getByTestId("question-legend").textContent()) ?? "";
  if (await page.getByTestId("question-text-input").isVisible()) {
    await page.getByTestId("question-text-input").fill("E2E answer");
  } else if (await page.getByTestId("question-yes").isVisible()) {
    if (legend.includes("medications")) {
      await page.getByTestId("question-yes").check();
      await expect(page.getByTestId("question-follow-up-input")).toBeVisible();
      await page.getByTestId("question-follow-up-input").fill("None regularly");
    } else {
      await page.getByTestId("question-no").check();
    }
  } else if (legend.includes("masculine or more feminine")) {
    await page.getByTestId(`question-option-${q4}`).check();
  } else {
    await page.locator('[data-testid^="question-option-"]').first().check();
  }
}

/** Answer every question up to the last one; returns the final total. */
async function answerAll(page: Page, q4: string): Promise<number> {
  for (;;) {
    const text = (await page.getByTestId("wizard-position").textContent()) ?? "";
    const [, current, total] = /Question (\d+) of (\d+)/.exec(text) ?? [];
    await answerCurrent(page, q4);
    if (current === total) return Number(total);
    await page.getByTestId("wizard-next-button").click();
    await expect(page.getByTestId("wizard-position")).toContainText(
      `Question ${Number(current) + 1} of`,
    );
  }
}

test("consent, answer every question with Q19 shown, confirm the disclaimer, submit @checkpoint", async ({
  page,
}) => {
  await signUp(page, "full");
  await expectAccessible(page, "home with the questionnaire link");
  await consent(page);
  await expectAccessible(page, "first question");

  const total = await answerAll(page, "masculine");
  expect(total).toBe(23); // Q4 = Masculine shows Q19
  await expect(page.getByTestId("disclaimer-text")).toContainText(DISCLAIMER_START);
  await expect(page.getByTestId("wizard-submit-button")).toBeDisabled();
  await expect(page.getByTestId("disclaimer-reason")).toBeVisible();
  await expectAccessible(page, "last question with the disclaimer");

  await page.getByTestId("disclaimer-checkbox").check();
  await page.getByTestId("wizard-submit-button").click();
  await expect(page.getByTestId("onboarding-submitted")).toBeVisible();
  await expectAccessible(page, "submitted");

  await page.getByTestId("onboarding-home-button").click();
  await expect(page.getByTestId("home-status")).toContainText("questionnaire is submitted");
  await expect(page.getByTestId("home-onboarding-link")).toHaveCount(0);
});

test("Q4 = Feminine skips Q19, answers resume after a reload, and the supportive message shows", async ({
  page,
}) => {
  await signUp(page, "branch");
  await consent(page);
  await page.getByTestId("question-text-input").fill("Designer");
  await page.getByTestId("wizard-next-button").click();
  await expect(page.getByTestId("wizard-position")).toHaveText("Question 2 of 22");
  await page.getByTestId("wizard-next-button").click(); // pick nothing
  await expect(page.getByTestId("question-error")).toHaveText(/Please choose an answer/);

  // Resume: a reload returns to the first unanswered question with answers kept.
  await page.reload();
  await expect(page.getByTestId("wizard-position")).toHaveText("Question 2 of 22");
  await page.getByTestId("wizard-back-button").click();
  await expect(page.getByTestId("question-text-input")).toHaveValue("Designer");
  await page.getByTestId("wizard-next-button").click();
  // Next saves the answer before it moves on: wait for Question 2, or answerAll would read the
  // previous position and run one question behind (a timing race found in U4).
  await expect(page.getByTestId("wizard-position")).toHaveText("Question 2 of 22");

  expect(await answerAll(page, "feminine")).toBe(22);
  await page.getByTestId("disclaimer-cannot-confirm-link").click();
  await expect(page.getByTestId("support-panel")).toContainText("Your answers are saved.");
  await expect(
    page.getByRole("heading", { name: "Thank you for being honest with us." }),
  ).toBeFocused();
  await expectAccessible(page, "supportive message");
  await page.getByTestId("support-panel-back-button").click();
  await expect(page.getByTestId("wizard-submit-button")).toBeDisabled();
});
