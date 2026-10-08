// The two main journeys end to end, with axe on every main screen (US1.13: AC1.13.2, AC1.13.3):
//   1. landing -> sign up -> emailed code -> questionnaire -> log out -> landing "Sign in" ->
//      log in -> back on the next step;
//   2. photos -> payment (Stripe fake) -> confirmation -> Start Analysis -> progress -> Home ->
//      report, then Settings.
// They run on a 360 px phone and a desktop viewport in Chromium, and in WebKit and Firefox
// (scripts/verify.sh and CI). Not tagged @checkpoint: the checkpoint run keeps its own subset.
// The Beauty Assistant (U9) is on the axe list. No paid service is called.
import { expect, test } from "@playwright/test";

import {
  PASSWORD,
  expectAccessible,
  latestCode,
  photo,
  signUpThroughTheUi,
  submitQuestionnaire,
} from "./helpers";

test("landing, sign up, questionnaire, log out, sign in again lands on the next step", async ({
  page,
}) => {
  // Landing: Get started, a header Sign in link and "How it works" in order (AC2.1.1, AC2.2.1).
  await page.goto("/");
  await expect(page.getByTestId("landing-get-started")).toBeVisible();
  await expect(page.getByTestId("landing-signin-link")).toBeVisible();
  await expect(page.locator('[data-testid^="how-step-"]')).toHaveCount(4);
  await expectAccessible(page, "landing");
  await page.getByTestId("landing-get-started").click();
  await expect(page).toHaveURL(/\/signup$/);
  await expectAccessible(page, "sign up");

  const email = await signUpThroughTheUi(page, "journey1", "Maya Journey");
  await expect(page).toHaveURL(/\/onboarding$/); // a new user lands on the questionnaire
  await expect(page.getByTestId("user-menu-name")).toHaveText("Maya Journey");
  await page.getByTestId("consent-checkbox").check();
  await page.getByTestId("consent-continue-button").click();
  await expect(page.getByTestId("wizard-position")).toContainText("Question 1 of");
  await expectAccessible(page, "questionnaire");

  // Log out (the shared confirmation dialog), then enter through the landing page's Sign in.
  await page.getByTestId("user-menu-button").click();
  await page.getByTestId("user-menu-logout").click();
  await page.getByTestId("confirm-dialog-confirm").click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/");
  await page.getByTestId("landing-signin-link").click();
  await expect(page).toHaveURL(/\/login$/); // not sign-up (AC2.1.2)
  await expectAccessible(page, "log in");
  await page.getByTestId("login-email-input").fill(email);
  await page.getByTestId("login-password-input").fill(PASSWORD);
  const sentAt = Date.now();
  await page.getByTestId("login-submit-button").click();
  await expect(page).toHaveURL(/\/verify$/);
  await expectAccessible(page, "enter your code");
  await page
    .getByTestId("verify-code-input")
    .fill(await latestCode(page, email, "Your sign-in code", sentAt));
  await page.getByTestId("verify-submit-button").click();
  await expect(page).toHaveURL(/\/onboarding$/); // the next step is still the questionnaire
  await expect(page.getByTestId("user-menu-name")).toHaveText("Maya Journey");
});

test("photos, payment, analysis, report and settings", async ({ page }) => {
  await signUpThroughTheUi(page, "journey2", "Sam Journey");
  await submitQuestionnaire(page.request);

  // Opening a later step's URL sends the user to the next unfinished one (AC11.8.2).
  await page.goto("/payment");
  await expect(page).toHaveURL(/\/photos$/);
  await expect(page.getByTestId("photo-requirements")).toBeVisible();
  await expectAccessible(page, "photo requirements");
  await page.getByTestId("photo-requirements-continue").click();
  const set = page.getByTestId("photo-file-input");
  await set.setInputFiles(photo("person-a-front.png"));
  await expect(page.getByTestId("photo-step-title")).toHaveText(/Photo 2 of 3/);
  await set.setInputFiles(photo("person-a-left.png"));
  await expect(page.getByTestId("photo-step-title")).toHaveText(/Photo 3 of 3/);
  await set.setInputFiles(photo("person-a-right.png"));
  await expect(page.getByTestId("photo-review")).toBeVisible();
  await expect(page.getByTestId("review-status")).toHaveText("All 3 photos look good.");
  await expectAccessible(page, "photo review");
  await page.getByTestId("review-continue-button").click();

  await expect(page).toHaveURL(/\/payment$/);
  await expectAccessible(page, "payment");
  await page.getByTestId("payment-pay-button").click();
  await expect(page).toHaveURL(/\/payments\/fake-checkout\/cs_fake_[0-9a-f]{24}$/);
  await page.getByTestId("fake-checkout-pay").click();
  await expect(page).toHaveURL(/\/payment\/success$/);
  await expect(page.getByTestId("payment-confirmation-title")).toHaveText("Payment confirmed", {
    timeout: 20_000,
  });
  await page.getByTestId("payment-start-analysis-button").click();

  await expect(page).toHaveURL(/\/analysis$/);
  await expect(page.getByTestId("analysis-progress")).toBeVisible();
  await expectAccessible(page, "analysis progress");
  await expect(page.getByTestId("analysis-view-report")).toBeVisible({ timeout: 90_000 });
  await page.getByTestId("analysis-view-report").click();

  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByTestId("home-overview")).toBeVisible();
  await expectAccessible(page, "Home");
  await page.getByTestId("home-report-link").click();
  await expect(page).toHaveURL(/\/report$/);
  await expect(page.locator('section[data-testid^="feature-"]')).toHaveCount(11);
  await expectAccessible(page, "report");

  // Chat (U9): empty state, then a question and the fake assistant's reply.
  if (await page.getByTestId("nav-menu-button").isVisible()) {
    await page.getByTestId("nav-menu-button").click();
  }
  await page.getByTestId("nav-chat").click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByTestId("chat-empty")).toBeVisible();
  await expectAccessible(page, "chat: empty state");
  await page.getByTestId("chat-input").fill("What does my symmetry score mean?");
  await page.getByTestId("chat-send-button").click();
  await expect(page.getByTestId("chat-log")).toContainText("This is a fake assistant reply.");
  await expectAccessible(page, "chat: with a reply");

  // Settings: Account Info and Billing (US11.4, US11.6), with the paid payment listed.
  await page.getByTestId("user-menu-button").click();
  await page.getByTestId("user-menu-settings-link").click();
  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByTestId("account-name")).toHaveText("Sam Journey");
  await expectAccessible(page, "settings: account info");
  await page.getByTestId("settings-tab-billing").click();
  await expect(page.getByTestId("billing-row")).toHaveCount(1);
  await expectAccessible(page, "settings: billing");
});
