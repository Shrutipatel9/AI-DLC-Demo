// U5 payment journey (US6.1, US6.2, US6.3, US6.5; FR-015, FR-016). Runs against the production
// web build and a running API on real PostgreSQL with the Stripe FAKE (`PAYMENT_PROVIDER=fake`,
// scripts/ci-env.sh): the fake serves a hosted test checkout page on the API, and "Pay" posts a
// webhook signed like Stripe's back to the API after a short delay
// (FAKE_PAYMENT_WEBHOOK_DELAY_SECONDS), so the confirming screen is seen before the
// confirmation. No paid service is called.
//
// The questionnaire and the three photos are submitted through the API (both have their own
// journeys) to keep the checkpoint run within its time budget; the photo review and its
// Continue button are then used in the browser. The price is the test configuration's
// REPORT_PRICE_AMOUNT / REPORT_PRICE_CURRENCY (2900 USD in scripts/ci-env.sh). The scenario
// tagged @checkpoint is part of scripts/verify-skeleton.sh; CI and verify.sh run all of them.
import { readFileSync } from "node:fs";
import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const MAILPIT_URL = process.env.MAILPIT_URL ?? "http://127.0.0.1:8025";
const API_ORIGIN = process.env.API_ORIGIN ?? "http://localhost:8000";
const WEB_ORIGIN = process.env.WEB_BASE_URL ?? "http://localhost:3000";
const PRICE_AMOUNT = Number(process.env.REPORT_PRICE_AMOUNT ?? "2900");
const PRICE_CURRENCY = process.env.REPORT_PRICE_CURRENCY ?? "USD";
const PASSWORD = "Sunrise2026x";
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const PHOTOS = path.resolve(__dirname, "fixtures", "photos");

/** The price as the payment screen shows it (en-US, the browser's default locale here). */
const DISPLAY_PRICE = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: PRICE_CURRENCY,
}).format(PRICE_AMOUNT / 100);

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

async function signUp(page: Page, label: string): Promise<void> {
  const email = `e2e-pay-${label}-${Date.now()}-${test.info().project.name}@example.test`;
  await page.goto("/signup");
  await page.getByTestId("signup-fullname-input").fill("Sam Payments");
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
  await expect(page.getByTestId("user-menu-name")).toHaveText("Sam Payments");
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

/** Consent, answer every visible question and submit; then upload the three same-person photos. */
async function readyForPayment(request: APIRequestContext): Promise<void> {
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
}

/** Sign up, get the questionnaire and photos ready, then Continue from the photo review. */
async function openPayment(page: Page, label: string) {
  await signUp(page, label);
  await readyForPayment(page.request);
  await page.goto("/photos");
  await expect(page.getByTestId("review-status")).toHaveText("All 3 photos look good.");
  await page.getByTestId("review-continue-button").click();
  await expect(page).toHaveURL(/\/payment$/);
  await expect(page.getByTestId("payment-price")).toHaveText(DISPLAY_PRICE);
}

/** Pay on the payment screen and land on the fake provider's hosted test page. */
async function toHostedCheckout(page: Page) {
  await page.getByTestId("payment-pay-button").click();
  await expect(page).toHaveURL(/\/payments\/fake-checkout\/cs_fake_[0-9a-f]{24}$/);
  await expect(page.getByTestId("fake-checkout-minor-units")).toHaveText(String(PRICE_AMOUNT));
}

test("payment screen, Stripe fake checkout, confirming, then confirmed @checkpoint", async ({
  page,
}) => {
  await openPayment(page, "happy");
  await expect(page.getByTestId("payment-includes")).toContainText("11 features");
  await expect(page.getByTestId("payment-start-note")).toContainText(
    "it starts only when you click Start Analysis",
  );
  await expectAccessible(page, "payment screen");

  await toHostedCheckout(page);
  await page.getByTestId("fake-checkout-pay").click();

  // Back from checkout before the webhook: confirming, Start Analysis unavailable (AC6.5.1).
  await expect(page).toHaveURL(/\/payment\/success$/);
  await expect(page.getByTestId("payment-confirmation-title")).toHaveText(
    "Confirming your payment",
  );
  await expect(page.getByTestId("payment-start-analysis-button")).toBeDisabled();
  await expectAccessible(page, "confirming payment");

  // The signed webhook arrives: the screen updates without a reload (AC6.5.2).
  await expect(page.getByTestId("payment-confirmation-title")).toHaveText("Payment confirmed", {
    timeout: 20_000,
  });
  await expect(page.getByTestId("payment-announcement")).toHaveText(
    "Your payment is confirmed. You can start your analysis.",
  );
  await expect(page.getByTestId("payment-start-analysis-button")).toBeEnabled();
  await expectAccessible(page, "payment confirmed");

  // The webhook never started anything: the payment is paid and nothing else happened.
  const headers = await apiHeaders(page.request);
  const status = await page.request.get(`${API_ORIGIN}/payments/status`, { headers });
  expect(((await status.json()) as { state: string }).state).toBe("paid");
});

test("cancel on the checkout page returns to payment with nothing charged", async ({ page }) => {
  await openPayment(page, "cancel");
  await toHostedCheckout(page);
  await page.getByTestId("fake-checkout-cancel").click();

  await expect(page).toHaveURL(/\/payment\/cancel$/);
  await expect(page.getByTestId("payment-cancelled-notice")).toHaveText(
    "Payment cancelled. You have not been charged.",
  );
  await expect(page.getByTestId("payment-price")).toHaveText(DISPLAY_PRICE);
  await expect(page.getByTestId("payment-pay-button")).toBeEnabled();
  await expectAccessible(page, "payment cancelled");

  const headers = await apiHeaders(page.request);
  const status = await page.request.get(`${API_ORIGIN}/payments/status`, { headers });
  expect(((await status.json()) as { state: string }).state).not.toBe("paid");
});
