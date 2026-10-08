// U2 session journey (NFR8.3, NFR9.6, NFR9.7, NFR9.9; US3.5, US3.7, US3.9, US3.11, US11.5,
// US11.7). Runs against the production web build and a running API; codes come from
// Mailpit. The one scenario tagged @checkpoint (two tabs refresh together, U2's core rule) is
// in the checkpoint subset (desktop only) of scripts/verify-skeleton.sh, which runs one journey
// per unit (U4 plan Step 9); CI and scripts/verify.sh run all of them at both viewports.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const MAILPIT_URL = process.env.MAILPIT_URL ?? "http://127.0.0.1:8025";
const PASSWORD = "Sunrise2026x";
const NEW_PASSWORD = "Moonrise2027y";
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

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

async function expectAccessible(page: Page, screen: string, include?: string) {
  let builder = new AxeBuilder({ page }).withTags(WCAG_TAGS);
  if (include) builder = builder.include(include);
  const results = await builder.analyze();
  expect(results.violations, `axe violations on ${screen}`).toEqual([]);
}

/** Sign up through the UI and land on the questionnaire (US11.8). Returns the email. */
async function signUp(page: Page, label: string): Promise<string> {
  const email = `e2e-${label}-${Date.now()}-${test.info().project.name}@example.test`;
  await page.goto("/signup");
  await page.getByTestId("signup-fullname-input").fill("Maya Session");
  await page.getByTestId("signup-email-input").fill(email);
  await page.getByTestId("signup-password-input").fill(PASSWORD);
  const sentAt = Date.now();
  await page.getByTestId("signup-submit-button").click();
  await expect(page).toHaveURL(/\/verify$/);
  await page
    .getByTestId("verify-code-input")
    .fill(await latestCode(page, email, "Your sign-up code", sentAt));
  await page.getByTestId("verify-submit-button").click();
  await expect(page.getByTestId("user-menu-name")).toHaveText("Maya Session");
  // The session tests below use the settings page: it is signed-in but not a journey step, so
  // their timing budgets measure only the session restore.
  await page.goto("/settings");
  await expect(page.getByTestId("user-menu-name")).toHaveText("Maya Session");
  return email;
}

async function logIn(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByTestId("login-email-input").fill(email);
  await page.getByTestId("login-password-input").fill(password);
  const sentAt = Date.now();
  await page.getByTestId("login-submit-button").click();
  await expect(page).toHaveURL(/\/verify$/);
  await page
    .getByTestId("verify-code-input")
    .fill(await latestCode(page, email, "Your sign-in code", sentAt));
  await page.getByTestId("verify-submit-button").click();
  await expect(page.getByTestId("user-menu-name")).toBeVisible();
}

async function expectNoWebStorage(page: Page) {
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
  }));
  expect(storage).toEqual({ local: 0, session: 0 });
}

async function openTab(context: BrowserContext, path: string): Promise<Page> {
  const page = await context.newPage();
  await page.goto(path);
  return page;
}

test("reload stays signed in, within 1.5 s", async ({ page }) => {
  await signUp(page, "reload");
  const started = Date.now();
  await page.reload();
  await expect(page.getByTestId("user-menu-name")).toHaveText("Maya Session");
  const elapsed = Date.now() - started;
  test.info().annotations.push({ type: "restore-ms", description: String(elapsed) });
  expect(elapsed, "session restore on reload (NFR9.6)").toBeLessThanOrEqual(1_500);
  await expectNoWebStorage(page);
});

test("two tabs refresh together without being logged out, both valid within 1 s @checkpoint", async ({
  page,
  context,
}) => {
  await signUp(page, "tabs");
  const second = await openTab(context, "/settings");
  await expect(second.getByTestId("user-menu-name")).toBeVisible();
  // Reload both at once: both restore at the same time; the lock lets one tab call
  // /auth/refresh and the other adopt its result, so strict reuse detection never fires.
  let refreshStartedAt = 0;
  context.on("request", (request) => {
    if (!refreshStartedAt && request.url().endsWith("/auth/refresh")) refreshStartedAt = Date.now();
  });
  await Promise.all([page.reload(), second.reload()]);
  await Promise.all([
    expect(page.getByTestId("user-menu-name")).toBeVisible(),
    expect(second.getByTestId("user-menu-name")).toBeVisible(),
  ]);
  const elapsed = Date.now() - refreshStartedAt;
  test.info().annotations.push({ type: "two-tab-ms", description: String(elapsed) });
  expect(elapsed, "both tabs hold a valid token (NFR9.7)").toBeLessThanOrEqual(1_000);
  // Neither tab was signed out: a further reload still restores in both.
  await second.reload();
  await expect(second.getByTestId("user-menu-name")).toBeVisible();
  await expectNoWebStorage(second);
});

test("logout in one tab signs out the other", async ({ page, context }) => {
  await signUp(page, "logout");
  const second = await openTab(context, "/settings");
  await expect(second.getByTestId("user-menu-name")).toBeVisible();
  await page.getByTestId("user-menu-button").click();
  await page.getByTestId("user-menu-logout").click();
  await expect(page.getByTestId("confirm-dialog")).toBeVisible();
  await expectAccessible(page, "logout dialog", '[data-testid="confirm-dialog"]');
  await page.getByTestId("confirm-dialog-confirm").click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByTestId("toast-success")).toContainText("logged out");
  await expectAccessible(page, "log in with a toast");
  await expect(second).toHaveURL(/\/login$/);
  // The revoked cookie cannot restore the session.
  await second.goto("/settings");
  await expect(second).toHaveURL(/\/login$/);
});

test("forgot password: code from Mailpit, reset, log in with the new password", async ({
  page,
  context,
}) => {
  const email = await signUp(page, "reset");
  await context.clearCookies();
  await page.goto("/login");
  await page.getByTestId("login-forgot-password-link").click();
  await expect(page).toHaveURL(/\/forgot-password$/);
  await expectAccessible(page, "forgot password");
  await page.getByTestId("forgot-password-email-input").fill(email);
  const sentAt = Date.now();
  await page.getByTestId("forgot-password-submit-button").click();
  await expect(page).toHaveURL(/\/forgot-password\/verify$/);
  await expectAccessible(page, "reset code");
  await page
    .getByTestId("verify-code-input")
    .fill(await latestCode(page, email, "Your password reset code", sentAt));
  await page.getByTestId("verify-submit-button").click();
  await expect(page).toHaveURL(/\/reset-password$/);
  await expectAccessible(page, "choose a new password");
  await page.getByTestId("reset-password-new-input").fill(NEW_PASSWORD);
  await page.getByTestId("reset-password-confirm-input").fill(NEW_PASSWORD);
  await page.getByTestId("reset-password-submit-button").click();
  await expect(page).toHaveURL(/\/login$/);
  await logIn(page, email, NEW_PASSWORD);
});

test("change password keeps this tab signed in", async ({ page }) => {
  await signUp(page, "change");
  await page.getByTestId("user-menu-button").click();
  await page.getByTestId("user-menu-password-link").click();
  await expect(page).toHaveURL(/\/settings\/password$/);
  await expectAccessible(page, "change password");
  await page.getByTestId("change-password-current-input").fill(PASSWORD);
  await page.getByTestId("change-password-new-input").fill(NEW_PASSWORD);
  await page.getByTestId("change-password-confirm-input").fill(NEW_PASSWORD);
  await page.getByTestId("change-password-submit-button").click();
  await expect(page.getByTestId("toast-success")).toContainText("password was changed");
  await page.reload();
  await expect(page.getByRole("heading", { name: "Change password" })).toBeVisible();
});
