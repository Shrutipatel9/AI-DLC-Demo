// U4 photo journey (US5.1, US5.2, US5.5, US5.6, US5.11; NFR9.6). Runs against the production web
// build and a running API with the real MediaPipe model; codes come from Mailpit.
//
// The photos are synthetic renders of MediaPipe's canonical face mesh (no real person), made by
// `backend/tools/make_face_fixtures.py`. The API runs with FACE_LANDMARK_OVERRIDES_FILE so the
// person-B photo reads as a different person ([Decided by delivery team]: MediaPipe pulls
// synthetic faces towards an average face; every other photo goes through the real model).
//
// The questionnaire is submitted through the API (it has its own journey in onboarding.spec.ts)
// to keep the checkpoint run within its time budget. The scenario tagged @checkpoint is part of
// the checkpoint subset in scripts/verify-skeleton.sh; CI and verify.sh run all of them.
import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const MAILPIT_URL = process.env.MAILPIT_URL ?? "http://127.0.0.1:8025";
const API_ORIGIN = process.env.API_ORIGIN ?? "http://localhost:8000";
const WEB_ORIGIN = process.env.WEB_BASE_URL ?? "http://localhost:3000";
const PASSWORD = "Sunrise2026x";
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const FIXTURES = path.resolve(__dirname, "fixtures", "photos");

const photo = (name: string) => path.join(FIXTURES, name);

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
  const email = `e2e-photos-${label}-${Date.now()}-${test.info().project.name}@example.test`;
  await page.goto("/signup");
  await page.getByTestId("signup-fullname-input").fill("Maya Photos");
  await page.getByTestId("signup-email-input").fill(email);
  await page.getByTestId("signup-password-input").fill(PASSWORD);
  const sentAt = Date.now();
  await page.getByTestId("signup-submit-button").click();
  await expect(page).toHaveURL(/\/verify$/);
  await page
    .getByTestId("verify-code-input")
    .fill(await latestCode(page, email, "Your sign-up code", sentAt));
  await page.getByTestId("verify-submit-button").click();
  await expect(page.getByTestId("home-greeting")).toHaveText("Hi, Maya Photos");
}

/**
 * Consent, answer every visible question and submit, through the API. The browser context's
 * refresh cookie (shared with `page.request`) gives this helper its own access token.
 */
async function submitQuestionnaire(request: APIRequestContext): Promise<void> {
  const refreshed = await request.post(`${API_ORIGIN}/auth/refresh`, {
    headers: { "X-Requested-With": "XMLHttpRequest", Origin: WEB_ORIGIN },
  });
  expect(refreshed.ok(), "refresh for the API helper").toBe(true);
  const { accessToken } = (await refreshed.json()) as { accessToken: string };
  const headers = { Authorization: `Bearer ${accessToken}`, "X-Requested-With": "XMLHttpRequest" };
  const api = (path: string) => `${API_ORIGIN}${path}`;

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

/** Sign up, submit the questionnaire, and open the photo step from the home page link. */
async function openPhotos(page: Page, label: string) {
  await signUp(page, label);
  await submitQuestionnaire(page.request);
  await page.reload();
  await expect(page.getByTestId("home-status")).toContainText("Next, add your photos.");
  await page.getByTestId("home-photos-link").click();
  await expect(page).toHaveURL(/\/photos$/);
  await expect(page.getByTestId("photo-requirements")).toBeVisible();
}

async function upload(page: Page, name: string, nextTitle: RegExp | null) {
  await page.getByTestId("photo-file-input").setInputFiles(photo(name));
  if (nextTitle) {
    await expect(page.getByTestId("photo-step-title")).toHaveText(nextTitle);
  }
}

async function expectThumbnailsLoaded(page: Page) {
  for (const angle of ["front", "left_3q", "right_3q"]) {
    await expect(
      page.getByTestId(`review-photo-${angle}`).locator('[data-state="loaded"] img'),
    ).toBeVisible();
  }
}

test("rules, three same-person photos, review consistent, Continue @checkpoint", async ({
  page,
}) => {
  await openPhotos(page, "happy");
  await expect(page.locator('[data-testid^="photo-rule-"]').filter({ hasText: /\w/ })).toHaveCount(
    7,
  );
  await expectAccessible(page, "photo requirements");

  await page.getByTestId("photo-requirements-continue").click();
  await expect(page.getByTestId("photo-step-title")).toHaveText("Photo 1 of 3: Front");
  await expect(page.getByTestId("photo-progress")).toHaveText("0 of 3 photos done");
  await expectAccessible(page, "front capture step");

  await upload(page, "person-a-front.png", /Photo 2 of 3: Left 3\/4/);
  await expect(page.getByTestId("photo-progress")).toHaveText("1 of 3 photos done");
  await expect(page.getByTestId("photo-announcement")).toHaveText(
    "Front photo accepted. Next: Left 3/4.",
  );
  await upload(page, "person-a-left.png", /Photo 3 of 3: Right 3\/4/);
  await upload(page, "person-a-right.png", null);

  await expect(page.getByTestId("photo-review")).toBeVisible();
  await expect(page.getByTestId("review-status")).toHaveText("All 3 photos look good.");
  await expectThumbnailsLoaded(page);
  await expect(page.getByTestId("review-continue-button")).toBeEnabled();
  await expectAccessible(page, "review, consistent");

  await page.getByTestId("review-continue-button").click();
  await expect(page).toHaveURL(/\/payment$/); // the payment step comes next (U5)
});

test("rejections: no face, and a file that is not an image", async ({ page }) => {
  await openPhotos(page, "reject");
  await page.getByTestId("photo-requirements-continue").click();

  await upload(page, "no-face.png", null);
  await expect(page.getByTestId("photo-reasons")).toContainText(
    "We couldn't find a face in this photo.",
  );
  await expect(page.getByTestId("photo-step-title")).toHaveText("Photo 1 of 3: Front");
  await expectAccessible(page, "rejected photo");

  // Named like a photo, but the bytes are text: the server decides by the bytes (415).
  await page.getByTestId("photo-file-input").setInputFiles({
    name: "holiday.png",
    mimeType: "image/png",
    buffer: Buffer.from("this is not an image"),
  });
  await expect(page.getByTestId("photo-reasons")).toContainText(
    "Please upload a JPEG, PNG or HEIC photo.",
  );

  // A reload shows the stored rejection again; a good photo then replaces it.
  await page.reload();
  await page.getByTestId("photo-requirements-continue").click();
  await expect(page.getByTestId("photo-reason-NO_FACE")).toBeVisible();
  await upload(page, "person-a-front.png", /Photo 2 of 3: Left 3\/4/);
});

test("a different person is flagged; retaking it enables Continue without moving on", async ({
  page,
}) => {
  await openPhotos(page, "mismatch");
  await page.getByTestId("photo-requirements-continue").click();
  await upload(page, "person-a-front.png", /Left 3\/4/);
  await upload(page, "person-b-left.png", /Right 3\/4/);
  await upload(page, "person-a-right.png", null);

  await expect(page.getByTestId("photo-review")).toBeVisible();
  await expect(page.getByTestId("review-photo-left_3q")).toHaveAttribute("data-flagged", "true");
  await expect(page.getByTestId("review-flag-left_3q")).toContainText(
    "These photos don't appear to show the same person.",
  );
  await expect(page.getByTestId("review-photo-front")).toHaveAttribute("data-flagged", "false");
  await expect(page.getByTestId("review-continue-button")).toBeDisabled();
  await expect(page.getByTestId("review-continue-reason")).toHaveText(
    "Retake the highlighted photo to continue.",
  );
  await expectAccessible(page, "review, mismatch");

  // A reload recomputes the result from the stored photos: still flagged.
  await page.reload();
  await expect(page.getByTestId("review-photo-left_3q")).toHaveAttribute("data-flagged", "true");

  await page.getByTestId("review-retake-left_3q").click();
  await expect(page.getByTestId("photo-step-title")).toHaveText("Photo 2 of 3: Left 3/4");
  await upload(page, "person-a-left.png", null);
  await expect(page.getByTestId("photo-review")).toBeVisible();
  await expect(page.getByTestId("review-continue-button")).toBeEnabled();
  await expect(page.getByTestId("review-photo-left_3q")).toHaveAttribute("data-flagged", "false");
  // No automatic navigation: the review stays until Continue is clicked (AC5.11.4).
  await page.waitForTimeout(1_000);
  await expect(page).toHaveURL(/\/photos$/);
});
