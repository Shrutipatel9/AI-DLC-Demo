// Walking-skeleton journey (US1.2, US3.1, US3.2, US3.4, US3.8; NFR8.4, NFR9.6, NFR9.7).
//
// sign up -> read the code from the Mailpit API -> verify -> "Hi, {name}" -> Web Storage is
// empty -> reload stays signed in (U2) -> log out -> log in -> code -> home. Every screen is checked with axe
// (WCAG 2.1 AA). The code is read from Mailpit, never from a test-only backend endpoint.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const MAILPIT_URL = process.env.MAILPIT_URL ?? "http://127.0.0.1:8025";
const PASSWORD = "Sunrise2026x";
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

interface MailpitSummary {
  ID: string;
  Created: string;
  Subject: string;
}

async function latestCode(
  page: Page,
  email: string,
  subject: string,
  after: number,
): Promise<string> {
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

async function expectAccessible(page: Page, screenName: string) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations, `axe violations on ${screenName}`).toEqual([]);
}

test("sign up, verify, see who I am, reload keeps me, log out, log in again @checkpoint", async ({
  page,
}, testInfo) => {
  const email = `e2e-${Date.now()}-${testInfo.project.name}@example.test`;
  const fullName = `Maya ${testInfo.project.name}`;

  // --- Sign up (step 1) --------------------------------------------------------------------
  await page.goto("/signup");
  await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();
  const csp = (await page.request.get("/signup")).headers()["content-security-policy"] ?? "";
  expect(csp).toContain("'strict-dynamic'");
  expect(csp).not.toContain("unsafe-eval");
  await expectAccessible(page, "sign up");

  await page.getByTestId("signup-fullname-input").fill(fullName);
  await page.getByTestId("signup-email-input").fill(email);
  await page.getByTestId("signup-password-input").fill(PASSWORD);
  const signupSentAt = Date.now();
  await page.getByTestId("signup-submit-button").click();

  // --- Verify (step 2) ---------------------------------------------------------------------
  await expect(page).toHaveURL(/\/verify$/);
  await expect(page.getByTestId("verify-masked-email")).toContainText("e•••@example.test");
  await expectAccessible(page, "enter your code");
  const signupCode = await latestCode(page, email, "Your sign-up code", signupSentAt);
  await page.getByTestId("verify-code-input").fill(signupCode);
  await page.getByTestId("verify-submit-button").click();

  // --- Signed in: "who am I" -----------------------------------------------------------------
  // US11.8: a new user lands on their next step, the questionnaire.
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByTestId("user-menu-name")).toHaveText(fullName);
  await expectAccessible(page, "consent");
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
  }));
  expect(storage).toEqual({ local: 0, session: 0 });
  const cookies = await page.context().cookies("http://localhost:8000/auth");
  const refresh = cookies.find((cookie) => cookie.name === "refresh_token");
  expect(refresh?.httpOnly).toBe(true);

  // --- Reload keeps the session (U2 WF-U2-2 replaces U1's "reload signs out") ----------------
  await page.reload();
  await expect(page.getByTestId("user-menu-name")).toHaveText(fullName);

  // --- Log out (confirmed in the shared dialog, U2 WF-U2-6) ------------------------------------
  await page.getByTestId("user-menu-button").click();
  await page.getByTestId("user-menu-logout").click();
  await page.getByTestId("confirm-dialog-confirm").click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
  await expectAccessible(page, "log in");

  // --- Log in again: password, then emailed code ---------------------------------------------
  await page.getByTestId("login-email-input").fill(email);
  await page.getByTestId("login-password-input").fill(PASSWORD);
  const loginSentAt = Date.now();
  await page.getByTestId("login-submit-button").click();
  await expect(page).toHaveURL(/\/verify$/);
  const loginCode = await latestCode(page, email, "Your sign-in code", loginSentAt);
  await page.getByTestId("verify-code-input").fill(loginCode);
  await page.getByTestId("verify-submit-button").click();
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByTestId("user-menu-name")).toHaveText(fullName);
});
