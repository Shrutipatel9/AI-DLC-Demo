// Playwright configuration for the walking-skeleton journey (NFR8.4, NFR9.6, NFR9.7).
// The journey runs against the PRODUCTION web build (`pnpm build && pnpm start`) and a
// running API, so the strict CSP is what gets tested. Codes are read from Mailpit.
import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.WEB_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    // Under reduced motion the CSS removes animations, so axe never samples a fading toast.
    contextOptions: { reducedMotion: "reduce" },
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "phone",
      use: { ...devices["Desktop Chrome"], viewport: { width: 360, height: 800 }, isMobile: false },
    },
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
    // U10 (AC1.13.2): the two main journeys also run in WebKit and Firefox, on a 360 px phone and
    // a desktop viewport. These four projects run only `journey.spec.ts`; the checkpoint run
    // (scripts/verify-skeleton.sh) uses the Chromium `desktop` project alone.
    ...(["webkit", "firefox"] as const).flatMap((engine) => {
      const base = engine === "webkit" ? devices["Desktop Safari"] : devices["Desktop Firefox"];
      return [
        {
          name: `phone-${engine}`,
          testMatch: /journey\.spec\.ts/,
          use: { ...base, viewport: { width: 360, height: 800 } },
        },
        {
          name: `desktop-${engine}`,
          testMatch: /journey\.spec\.ts/,
          use: { ...base, viewport: { width: 1280, height: 800 } },
        },
      ];
    }),
  ],
});
