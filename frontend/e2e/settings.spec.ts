// Settings in the browser (US11.4, US11.5, US11.6): Account Info without an edit control, the
// change-password section, and Billing with Stripe available and PayPal visible but disabled
// (activating it does nothing). Desktop and phone, with axe. No paid service is called.
import { expect, test } from "@playwright/test";

import {
  expectAccessible,
  payThroughTheFake,
  signUpThroughTheUi,
  submitQuestionnaire,
  uploadConsistentPhotos,
} from "./helpers";

test("account info is read only, billing lists payments, PayPal is disabled", async ({ page }) => {
  const email = await signUpThroughTheUi(page, "settings", "Maya Settings");
  await expect(page.getByTestId("user-menu-name")).toHaveText("Maya Settings");

  await page.goto("/settings");
  await expect(page.getByTestId("account-name")).toHaveText("Maya Settings");
  await expect(page.getByTestId("account-email")).toHaveText(email);
  await expect(page.getByTestId("account-verified")).toHaveText("Verified");
  await expect(page.getByTestId("account-member-since")).not.toBeEmpty();
  await expect(page.getByTestId("account-info").getByRole("textbox")).toHaveCount(0); // AC11.4.2
  await expectAccessible(page, "settings: account info");

  await page.getByTestId("settings-tab-password").click();
  await expect(page).toHaveURL(/\/settings\/password$/);
  await expect(page.getByRole("heading", { name: "Change password" })).toBeVisible();
  await expectAccessible(page, "settings: password");

  await page.getByTestId("settings-tab-billing").click();
  await expect(page).toHaveURL(/\/settings\/billing$/);
  await expect(page.getByTestId("billing-empty")).toBeVisible();
  await expect(page.getByTestId("payment-option-stripe")).toContainText("Available");
  const paypal = page.getByTestId("payment-option-paypal");
  await expect(paypal).toHaveAttribute("aria-disabled", "true");
  await expect(paypal).toHaveAccessibleDescription("Not available");
  await paypal.click({ force: true }); // Playwright treats aria-disabled as not enabled
  await expect(page).toHaveURL(/\/settings\/billing$/); // activating PayPal does nothing
  await expectAccessible(page, "settings: billing");

  // A payment made through the Stripe fake appears with its date, amount, currency and status.
  await submitQuestionnaire(page.request);
  await uploadConsistentPhotos(page.request);
  await payThroughTheFake(page.request);
  await page.reload();
  await expect(page.getByTestId("billing-row")).toHaveCount(1);
  await expect(page.getByTestId("billing-row")).toContainText("USD");
});
