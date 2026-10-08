// U9 Beauty Assistant journeys (US10.1, US10.3): a failed reply keeps the message, the input and
// the latest reply stay visible on a short (keyboard-open) phone screen, and the daily limit shows
// when chat reopens. Runs against the production web build, a running API and a REAL worker on
// real PostgreSQL, with the AI FAKE (`AI_TEXT_PROVIDER=fake`): a `fail-text` control file in
// `AI_FAKE_CONTROL_DIR` (read by the API and the worker) makes the next text call fail. No paid
// service is called. The @checkpoint chat step lives in analysis.spec.ts.
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import {
  API_ORIGIN,
  apiHeaders,
  expectAccessible,
  payThroughTheFake,
  signUpThroughTheUi,
  submitQuestionnaire,
  uploadConsistentPhotos,
} from "./helpers";

const CONTROL_DIR = process.env.AI_FAKE_CONTROL_DIR ?? "";
const DAILY_LIMIT = 50;

/** A paid user with a finished report, ready to chat. */
async function userWithReport(page: Page, label: string) {
  await signUpThroughTheUi(page, label, "Chat Tester");
  await submitQuestionnaire(page.request);
  await uploadConsistentPhotos(page.request);
  await payThroughTheFake(page.request);
  await page.goto("/payment/success");
  await expect(page.getByTestId("payment-confirmation-title")).toHaveText("Payment confirmed", {
    timeout: 20_000,
  });
  await page.getByTestId("payment-start-analysis-button").click();
  await expect(page.getByTestId("analysis-view-report")).toBeVisible({ timeout: 90_000 });
  await page.goto("/chat");
  await expect(page.getByTestId("chat-empty")).toBeVisible();
}

test("a failed reply keeps my message, and the input and reply stay visible on a short screen", async ({
  page,
}) => {
  expect(CONTROL_DIR, "AI_FAKE_CONTROL_DIR must point at the API's control directory").not.toBe("");
  await userWithReport(page, "chatfail");

  // The next text call fails: the message stays on screen with an error toast (AC10.1.4).
  // eslint-disable-next-line security/detect-non-literal-fs-filename -- the control directory comes from the test environment, not user input
  mkdirSync(CONTROL_DIR, { recursive: true });
  // eslint-disable-next-line security/detect-non-literal-fs-filename -- the control directory comes from the test environment, not user input
  writeFileSync(path.join(CONTROL_DIR, "fail-text"), "1", "utf-8");
  await page.getByTestId("chat-input").fill("Will this one fail?");
  await page.getByTestId("chat-send-button").click();
  await expect(page.getByTestId("toast-error")).toBeVisible();
  await expect(page.getByTestId("chat-message-failed")).toBeVisible();
  await expect(page.getByTestId("chat-log")).toContainText("Will this one fail?");
  await expect(page.getByTestId("chat-remaining")).toHaveText("50 messages left today");

  // The message is still there after a reload, and the next one is answered (AC10.1.2).
  await page.reload();
  await expect(page.getByTestId("chat-log")).toContainText("Will this one fail?");
  await page.getByTestId("chat-input").fill("And this one?");
  await page.getByTestId("chat-send-button").click();
  await expect(page.getByTestId("chat-log")).toContainText("This is a fake assistant reply.");
  await expect(page.getByTestId("chat-remaining")).toHaveText("49 messages left today");

  // A phone with the keyboard open leaves little height: input and latest reply stay visible (AC10.1.6).
  await page.setViewportSize({ width: 360, height: 420 });
  await expect(page.getByTestId("chat-input")).toBeInViewport();
  await expect(page.getByTestId("chat-message-assistant").last()).toBeInViewport();
});

test("after the daily limit the screen says when chat reopens", async ({ page }) => {
  await userWithReport(page, "chatlimit");
  const headers = await apiHeaders(page.request);
  for (let sent = 0; sent < DAILY_LIMIT; sent += 1) {
    const response = await page.request.post(`${API_ORIGIN}/chat/messages`, {
      headers,
      data: { text: `Question ${sent + 1}` },
    });
    expect(response.status(), `message ${sent + 1}`).toBe(200);
  }

  const refused = await page.request.post(`${API_ORIGIN}/chat/messages`, {
    headers,
    data: { text: "One too many" },
  });
  expect(refused.status()).toBe(429);
  expect(((await refused.json()) as { error: { code: string } }).error.code).toBe(
    "CHAT_DAILY_LIMIT_REACHED",
  );

  await page.reload();
  await expect(page.getByTestId("chat-limit")).toContainText("Chat reopens");
  await expect(page.getByTestId("chat-input")).toHaveCount(0);
  await expect(page.getByTestId("chat-remaining")).toHaveText("0 messages left today");
  await expectAccessible(page, "chat: daily limit reached");
});
