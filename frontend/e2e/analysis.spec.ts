// U6 analysis journey (US7.1, US7.2, US7.11; US1.7). Runs against the production web build, a
// running API and a REAL worker process on real PostgreSQL, with the AI FAKE (`AI_TEXT_PROVIDER=fake`,
// scripts/ci-env.sh): the worker pauses a couple of seconds per text call
// (`AI_FAKE_TEXT_DELAY_SECONDS`) so the progress screen is seen advancing, and a `fail-text`
// control file in `AI_FAKE_CONTROL_DIR` makes the next text calls fail (the re-run scenario).
// No paid service is called.
//
// To keep the checkpoint run within its time budget, the questionnaire and the three photos are
// submitted through the API (both have their own journeys) and the payment is made through the
// fake provider's own routes; the browser then uses the confirmation screen's real "Start
// Analysis" button and the progress screen. The scenario tagged @checkpoint is part of
// scripts/verify-skeleton.sh; CI and verify.sh run all of them.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const MAILPIT_URL = process.env.MAILPIT_URL ?? "http://127.0.0.1:8025";
const API_ORIGIN = process.env.API_ORIGIN ?? "http://localhost:8000";
const WEB_ORIGIN = process.env.WEB_BASE_URL ?? "http://localhost:3000";
const CONTROL_DIR = process.env.AI_FAKE_CONTROL_DIR ?? "";
const PASSWORD = "Sunrise2026x";
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const PHOTOS = path.resolve(__dirname, "fixtures", "photos");
const STEPS = ["measuring", "writing", "generating_images", "assembling"];

interface MailpitSummary {
  ID: string;
  Created: string;
}

interface Question {
  id: string;
  type: "text" | "single" | "multi" | "yesno";
  options?: { value: string }[];
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

async function signUp(page: Page, label: string): Promise<string> {
  const email = `e2e-analysis-${label}-${Date.now()}-${test.info().project.name}@example.test`;
  await page.goto("/signup");
  await page.getByTestId("signup-fullname-input").fill("Sam Analysis");
  await page.getByTestId("signup-email-input").fill(email);
  await page.getByTestId("signup-password-input").fill(PASSWORD);
  const sentAt = Date.now();
  await page.getByTestId("signup-submit-button").click();
  await expect(page).toHaveURL(/\/verify$/);
  await page
    .getByTestId("verify-code-input")
    .fill(await latestCode(page, email, "Your sign-up code", sentAt));
  await page.getByTestId("verify-submit-button").click();
  // US11.8: a new user lands on the questionnaire; the user menu shows who is signed in.
  await expect(page.getByTestId("user-menu-name")).toHaveText("Sam Analysis");
  return email;
}

/** API headers with a fresh access token from the browser context's refresh cookie. */
async function apiHeaders(request: APIRequestContext): Promise<Record<string, string>> {
  const refreshed = await request.post(`${API_ORIGIN}/auth/refresh`, {
    headers: { "X-Requested-With": "XMLHttpRequest", Origin: WEB_ORIGIN },
  });
  expect(refreshed.ok(), "refresh for the API helper").toBe(true);
  const { accessToken } = (await refreshed.json()) as { accessToken: string };
  return { Authorization: `Bearer ${accessToken}`, "X-Requested-With": "XMLHttpRequest" };
}

/** Consent, answer every visible question, submit, upload the three photos, and pay. */
async function readyAndPaid(request: APIRequestContext): Promise<void> {
  const headers = await apiHeaders(request);
  const api = (route: string) => `${API_ORIGIN}${route}`;

  const consent = (await (await request.get(api("/onboarding/consent"), { headers })).json()) as {
    consentTextVersion: string;
  };
  const given = await request.post(api("/onboarding/consent"), {
    headers,
    data: { consentTextVersion: consent.consentTextVersion },
  });
  expect(given.status()).toBe(201);
  const definition = (await (
    await request.get(api("/onboarding/questionnaire"), { headers })
  ).json()) as { questions: Question[] };
  let visible = new Set(definition.questions.map((question) => question.id));
  for (const question of definition.questions) {
    if (!visible.has(question.id)) continue;
    const value =
      question.type === "text"
        ? "E2E answer"
        : question.type === "yesno"
          ? false
          : question.type === "multi"
            ? [question.options?.[0]?.value ?? ""]
            : (question.options?.[0]?.value ?? "");
    const saved = await request.put(api(`/onboarding/response/answers/${question.id}`), {
      headers,
      data: { value },
    });
    expect(saved.ok(), `answer ${question.id}`).toBe(true);
    visible = new Set(
      ((await saved.json()) as { visibleQuestionIds: string[] }).visibleQuestionIds,
    );
  }
  const submitted = await request.post(api("/onboarding/response/submit"), {
    headers,
    data: { disclaimerConfirmed: true },
  });
  expect(submitted.ok(), "submit the questionnaire").toBe(true);

  for (const [angle, file] of [
    ["front", "person-a-front.png"],
    ["left_3q", "person-a-left.png"],
    ["right_3q", "person-a-right.png"],
  ]) {
    const uploaded = await request.put(api(`/photos/${angle}`), {
      headers,
      multipart: {
        file: {
          name: file,
          mimeType: "image/png",
          // eslint-disable-next-line security/detect-non-literal-fs-filename -- fixed fixture names under e2e/fixtures/photos, not user input
          buffer: readFileSync(path.join(PHOTOS, file)),
        },
        captureMethod: "upload",
      },
    });
    expect(uploaded.ok(), `upload ${angle}`).toBe(true);
  }

  // Pay through the Stripe fake's own routes; its signed webhook arrives a few seconds later.
  const checkout = await request.post(api("/payments/checkout"), { headers });
  expect(checkout.status()).toBe(201);
  const { checkoutUrl } = (await checkout.json()) as { checkoutUrl: string };
  const paid = await request.post(`${checkoutUrl}/pay`, { maxRedirects: 0 });
  expect(paid.status()).toBe(303);
}

/** Sign up, get ready and paid, wait for the confirmation and click "Start Analysis". */
async function startAnalysis(page: Page, label: string, afterSignUp?: () => Promise<void>) {
  const email = await signUp(page, label);
  await afterSignUp?.();
  await readyAndPaid(page.request);
  await page.goto("/payment/success");
  await expect(page.getByTestId("payment-confirmation-title")).toHaveText("Payment confirmed", {
    timeout: 20_000,
  });
  await page.getByTestId("payment-start-analysis-button").click();
  await expect(page).toHaveURL(/\/analysis$/);
  return email;
}

test("start the analysis, watch the worker advance every step, then view the report @checkpoint", async ({
  page,
}) => {
  const email = await startAnalysis(page, "happy", async () => {
    // U10, AC11.8.2: opening a later step's URL before the questionnaire sends the user back.
    await page.goto("/report");
    await expect(page).toHaveURL(/\/onboarding$/);
  });

  // The run is going in the background worker: steps in words, a leave-and-come-back note (AC7.2.1, AC7.2.2).
  await expect(page.getByTestId("analysis-progress")).toHaveAttribute("data-status", "running");
  await expect(page.getByTestId("analysis-step-label")).toHaveText("Step 5 of 5 · Analysis");
  await expect(page.getByTestId("analysis-leave-note")).toContainText(
    "close this page and come back later",
  );
  await expectAccessible(page, "analysis in progress");

  // The steps advance: measuring is done before the whole run is (AC7.6.1).
  await expect(page.getByTestId("analysis-step-measuring-state")).toHaveText("Done");

  // Ready: "View my report", announced politely (AC7.2.4).
  await expect(page.getByTestId("analysis-view-report")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("analysis-announcement")).toHaveText("Your report is ready.");
  for (const step of STEPS) {
    await expect(page.getByTestId(`analysis-step-${step}-state`)).toHaveText("Done");
  }

  // U7: the 13 AI Visuals images (5 hairstyles, 5 outfits, 3 aging cards) are shown, each labelled
  // as an AI illustration, next to the user's own photo (AC9.2.1, AC9.3.1, AC9.4.1, AC9.4.2).
  await page.getByTestId("analysis-visuals-link").click();
  await expect(page).toHaveURL(/\/visuals$/);
  await expect(page.getByTestId("visuals")).toBeVisible();
  await expect(page.locator('[data-testid^="visual-ai-label-"]')).toHaveCount(13);
  await expect(page.locator('[data-testid^="visual-image-"][data-state="loaded"]')).toHaveCount(14);
  await expectAccessible(page, "AI Visuals");
  await page.goBack();

  await expect(page.getByTestId("analysis-view-report")).toBeVisible();
  await page.getByTestId("analysis-view-report").click();
  await expect(page).toHaveURL(/\/home$/);

  // U8: a user with a report lands on Home Overview (AC11.1.1): stats, priorities, protocol and the
  // radar chart with its text alternative (AC11.1.2, AC11.1.4); the header links are all there.
  await expect(page.getByTestId("home-overview")).toBeVisible();
  await expect(page.getByTestId("home-stat-score")).toContainText("/100");
  await expect(page.getByTestId("home-protocol")).toContainText("PHASE 01");
  await expect(page.getByTestId("radar-values")).toContainText("Symmetry");
  await expect(page.locator('[data-testid^="home-priority-"]')).toHaveCount(3);
  // On a phone the four links sit behind the Menu button (AC11.2.2); open it first.
  if (await page.getByTestId("nav-menu-button").isVisible()) {
    await page.getByTestId("nav-menu-button").click();
  }
  for (const link of ["home", "report", "visuals", "chat"]) {
    await expect(page.getByTestId(`nav-${link}`)).toBeVisible();
  }
  await expect(page.getByTestId("home-before-image")).toHaveAttribute("data-state", "loaded");
  await expectAccessible(page, "Home Overview");

  // The report: the preamble first, then the 11 features in order, each with an AI-labelled
  // "after" image (AC8.1.1, AC8.7.2, AC8.7.4); the PDF downloads (AC8.5.1).
  await page.getByTestId("home-report-link").click();
  await expect(page).toHaveURL(/\/report$/);
  await expect(page.getByTestId("report-preamble")).toBeVisible();
  await expect(page.locator('section[data-testid^="feature-"]')).toHaveCount(11);
  await expect(page.getByTestId("feature-after-nose")).toHaveAttribute("data-state", "loaded");
  await expect(page.getByTestId("feature-ai-label-nose")).toHaveText("AI-generated illustration");
  await page.getByTestId("toc-jaw").click();
  await expect(page.getByRole("heading", { level: 3, name: "Jaw" })).toBeFocused();
  await expectAccessible(page, "report");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("report-download-pdf").click(),
  ]);
  expect(download.suggestedFilename()).toBe("facial-analysis-report.pdf");

  // U9: open Chat from the header, ask about the report and see the (fake) assistant's reply
  // (AC10.1.1, AC10.1.3, AC10.1.5); focus stays in the input while the reply is announced.
  if (await page.getByTestId("nav-menu-button").isVisible()) {
    await page.getByTestId("nav-menu-button").click();
  }
  await page.getByTestId("nav-chat").click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByTestId("chat-empty")).toBeVisible();
  await expectAccessible(page, "chat");
  await page.getByTestId("chat-input").fill("What does my symmetry score mean?");
  await page.getByTestId("chat-send-button").click();
  await expect(page.getByTestId("chat-log")).toContainText("This is a fake assistant reply.");
  await expect(page.getByTestId("chat-input")).toBeFocused();
  await expect(page.getByTestId("chat-remaining")).toHaveText("49 messages left today");

  // U10: log out, enter through the landing page's "Sign in" link, and sign-in lands on the next
  // step, which for a finished report is Home (US2.1 AC2.1.2, US11.8).
  await page.getByTestId("user-menu-button").click();
  await page.getByTestId("user-menu-logout").click();
  await page.getByTestId("confirm-dialog-confirm").click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/");
  await expect(page.getByTestId("landing-get-started")).toBeVisible();
  await page.getByTestId("landing-signin-link").click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByTestId("login-email-input").fill(email);
  await page.getByTestId("login-password-input").fill(PASSWORD);
  const loginSentAt = Date.now();
  await page.getByTestId("login-submit-button").click();
  await expect(page).toHaveURL(/\/verify$/);
  await page
    .getByTestId("verify-code-input")
    .fill(await latestCode(page, email, "Your sign-in code", loginSentAt));
  await page.getByTestId("verify-submit-button").click();
  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByTestId("home-overview")).toBeVisible();
});

test("a failed analysis is explained and the one free re-run completes it", async ({ page }) => {
  expect(CONTROL_DIR, "AI_FAKE_CONTROL_DIR must point at the worker's control directory").not.toBe(
    "",
  );
  // eslint-disable-next-line security/detect-non-literal-fs-filename -- the control directory comes from the test environment, not user input
  mkdirSync(CONTROL_DIR, { recursive: true });
  // All three text attempts of the first run fail; the free re-run then succeeds.
  // eslint-disable-next-line security/detect-non-literal-fs-filename -- the control directory comes from the test environment, not user input
  writeFileSync(path.join(CONTROL_DIR, "fail-text"), "3", "utf-8");

  await startAnalysis(page, "rerun");

  await expect(page.getByTestId("analysis-failed")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("analysis-failure-message")).toContainText(
    "went wrong on our side",
  );
  await expect(page.getByTestId("analysis-failure-message")).toContainText(
    "payment still covers this report",
  );
  await expect(page.getByTestId("analysis-step-writing-state")).toHaveText("Didn't finish");
  await expect(page.getByTestId("analysis-step-measuring-state")).toHaveText("Done");
  await expectAccessible(page, "analysis failed");

  await page.getByTestId("analysis-rerun-button").click();
  await expect(page.getByTestId("analysis-view-report")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("analysis-rerun-button")).toHaveCount(0);
  await expectAccessible(page, "analysis ready");

  // Coming back later shows the same finished run (AC7.2.3).
  await page.reload();
  await expect(page.getByTestId("analysis-view-report")).toBeVisible();
});

test("images that failed show Not available yet, and one retry brings the image back", async ({
  page,
}) => {
  expect(CONTROL_DIR, "AI_FAKE_CONTROL_DIR must point at the worker's control directory").not.toBe(
    "",
  );
  // eslint-disable-next-line security/detect-non-literal-fs-filename -- the control directory comes from the test environment, not user input
  mkdirSync(CONTROL_DIR, { recursive: true });
  const marker = path.join(CONTROL_DIR, "fail-image");
  // Every image call of this run fails (24 images x 4 attempts); the API's own retry does not.
  // eslint-disable-next-line security/detect-non-literal-fs-filename -- the control directory comes from the test environment, not user input
  writeFileSync(marker, "96", "utf-8");

  await startAnalysis(page, "images");
  // The report is published even though no image could be made (AC9.5.2).
  await expect(page.getByTestId("analysis-view-report")).toBeVisible({ timeout: 60_000 });
  // eslint-disable-next-line security/detect-non-literal-fs-filename -- the control directory comes from the test environment, not user input
  writeFileSync(marker, "0", "utf-8");

  await page.getByTestId("analysis-visuals-link").click();
  await expect(page).toHaveURL(/\/visuals$/);
  await expect(page.getByTestId("visual-unavailable-hairstyle_1")).toContainText(
    "Not available yet",
  );
  await expect(page.getByTestId("visual-retry-help-hairstyle_1")).toHaveText("3 retries left.");
  await expectAccessible(page, "AI Visuals with images not available yet");

  await page.getByTestId("visual-retry-hairstyle_1").click();
  await expect(page.getByTestId("visual-image-hairstyle_1")).toHaveAttribute(
    "data-state",
    "loaded",
  );
  await expect(page.getByTestId("visual-ai-label-hairstyle_1")).toHaveText(
    "AI-generated illustration",
  );
  // The other images are untouched: still marked, with all their retries.
  await expect(page.getByTestId("visual-unavailable-hairstyle_2")).toBeVisible();
});
