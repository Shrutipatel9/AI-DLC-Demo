// Shared helpers for the U10 journeys (journey.spec.ts, settings.spec.ts). Codes are read from
// Mailpit; the questionnaire is submitted through the API (its own journey covers the UI), and
// every screen is checked with axe against WCAG 2.1 AA. No paid service is called.
import { readFileSync } from "node:fs";
import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

export const MAILPIT_URL = process.env.MAILPIT_URL ?? "http://127.0.0.1:8025";
export const API_ORIGIN = process.env.API_ORIGIN ?? "http://localhost:8000";
export const WEB_ORIGIN = process.env.WEB_BASE_URL ?? "http://localhost:3000";
export const PASSWORD = "Sunrise2026x";
export const PHOTOS = path.resolve(__dirname, "fixtures", "photos");
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

interface MailpitSummary {
  ID: string;
  Created: string;
}

interface Question {
  id: string;
  type: "text" | "single" | "multi" | "yesno";
  options?: { value: string }[];
}

export async function latestCode(page: Page, email: string, subject: string, after: number) {
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

/** Axe must find no WCAG 2.1 A/AA violation on the screen as it is now (AC1.13.3). */
export async function expectAccessible(page: Page, screen: string) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, `axe violations on ${screen}`).toEqual([]);
}

/** Fill the sign-up form and the emailed code; lands on the user's next step. Returns the email. */
export async function signUpThroughTheUi(page: Page, label: string, fullName: string) {
  const email = `e2e-${label}-${Date.now()}-${test.info().project.name}@example.test`;
  await page.goto("/signup");
  await page.waitForLoadState("networkidle"); // let the form hydrate before typing (WebKit)
  const name = page.getByTestId("signup-fullname-input");
  const emailInput = page.getByTestId("signup-email-input");
  const password = page.getByTestId("signup-password-input");
  await expect(async () => {
    await name.fill(fullName);
    await emailInput.fill(email);
    await password.fill(PASSWORD);
    await expect(name).toHaveValue(fullName, { timeout: 1_000 });
    await expect(emailInput).toHaveValue(email, { timeout: 1_000 });
    await expect(password).toHaveValue(PASSWORD, { timeout: 1_000 });
  }).toPass({ timeout: 10_000 });
  const sentAt = Date.now();
  await page.getByTestId("signup-submit-button").click();
  await expect(page).toHaveURL(/\/verify$/);
  await page
    .getByTestId("verify-code-input")
    .fill(await latestCode(page, email, "Your FaceIQ sign-up code", sentAt));
  await page.getByTestId("verify-submit-button").click();
  // Signed in once the app shell shows the user menu; the refresh cookie exists from then on.
  await expect(page.getByTestId("user-menu-name")).toHaveText(fullName);
  return email;
}

/** API headers with a fresh access token from the browser context's refresh cookie. */
export async function apiHeaders(request: APIRequestContext): Promise<Record<string, string>> {
  const refreshed = await request.post(`${API_ORIGIN}/auth/refresh`, {
    headers: { "X-Requested-With": "XMLHttpRequest", Origin: WEB_ORIGIN },
  });
  expect(refreshed.ok(), "refresh for the API helper").toBe(true);
  const { accessToken } = (await refreshed.json()) as { accessToken: string };
  return { Authorization: `Bearer ${accessToken}`, "X-Requested-With": "XMLHttpRequest" };
}

/** Consent, answer every visible question and submit, through the API. */
export async function submitQuestionnaire(request: APIRequestContext): Promise<void> {
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
}

/** The path of a committed photo fixture. */
export function photo(name: string): string {
  return path.join(PHOTOS, name);
}

/** Upload the three same-person photos through the API. */
export async function uploadConsistentPhotos(request: APIRequestContext): Promise<void> {
  const headers = await apiHeaders(request);
  for (const [angle, file] of [
    ["front", "person-a-front.png"],
    ["left_3q", "person-a-left.png"],
    ["right_3q", "person-a-right.png"],
  ]) {
    const uploaded = await request.put(`${API_ORIGIN}/photos/${angle}`, {
      headers,
      multipart: {
        file: {
          name: file,
          mimeType: "image/png",
          // eslint-disable-next-line security/detect-non-literal-fs-filename -- fixed fixture names under e2e/fixtures/photos, not user input
          buffer: readFileSync(photo(file)),
        },
        captureMethod: "upload",
      },
    });
    expect(uploaded.ok(), `upload ${angle}`).toBe(true);
  }
}

/** Pay through the Stripe fake's own routes; its signed webhook arrives a few seconds later. */
export async function payThroughTheFake(request: APIRequestContext): Promise<void> {
  const headers = await apiHeaders(request);
  const checkout = await request.post(`${API_ORIGIN}/payments/checkout`, { headers });
  expect(checkout.status()).toBe(201);
  const { checkoutUrl } = (await checkout.json()) as { checkoutUrl: string };
  const paid = await request.post(`${checkoutUrl}/pay`, { maxRedirects: 0 });
  expect(paid.status()).toBe(303);
}
