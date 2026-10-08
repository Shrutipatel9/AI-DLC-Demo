// Settings: the sections, Account Info and Billing (US11.4, US11.6; FR-021, BR-012).
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { errorResponse, jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks } from "@/test-utils/next-mocks";

import { AccountInfoPanel } from "./account-info";
import { BillingPanel } from "./billing-panel";
import { formatDate, statusText } from "./format";
import { SettingsNav } from "./settings-shell";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});

const ACCOUNT = {
  fullName: "Maya Test",
  email: "maya@example.test",
  isVerified: true,
  memberSince: "2026-10-01T10:00:00Z",
};

describe("SettingsNav", () => {
  it("links the three sections and marks the current one", () => {
    render(<SettingsNav current="/settings/billing" />);
    expect(screen.getByTestId("settings-tab-account")).toHaveAttribute("href", "/settings");
    expect(screen.getByTestId("settings-tab-password")).toHaveAttribute(
      "href",
      "/settings/password",
    );
    expect(screen.getByTestId("settings-tab-billing")).toHaveAttribute("aria-current", "page");
    expect(screen.getByTestId("settings-tab-account")).not.toHaveAttribute("aria-current");
  });
});

describe("AccountInfoPanel", () => {
  beforeEach(() => {
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("shows name, email, verification status and member-since, with no edit control (AC11.4.1, AC11.4.2)", async () => {
    mockFetch(route("GET", "/settings/account", () => jsonResponse(200, ACCOUNT)));
    render(<AccountInfoPanel />);
    expect(await screen.findByTestId("account-name")).toHaveTextContent("Maya Test");
    expect(screen.getByTestId("account-email")).toHaveTextContent("maya@example.test");
    expect(screen.getByTestId("account-verified")).toHaveTextContent("Verified");
    expect(screen.getByTestId("account-member-since")).toHaveTextContent("2026");
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("says when the account cannot be loaded and tries again", async () => {
    let fail = true;
    mockFetch(
      route("GET", "/settings/account", () =>
        fail ? errorResponse(500, "INTERNAL_ERROR") : jsonResponse(200, ACCOUNT),
      ),
    );
    render(<AccountInfoPanel />);
    expect(await screen.findByRole("alert")).toHaveTextContent("couldn't load your account");
    fail = false;
    await userEvent.setup().click(screen.getByTestId("account-retry-button"));
    expect(await screen.findByTestId("account-name")).toHaveTextContent("Maya Test");
  });
});

describe("BillingPanel", () => {
  beforeEach(() => {
    resetNextMocks();
    configureApiOrigin("http://api.test");
  });

  it("lists payments with date, amount, currency and status (AC11.6.1)", async () => {
    mockFetch(
      route("GET", "/settings/billing", () =>
        jsonResponse(200, {
          payments: [
            { date: "2026-10-02T09:00:00Z", amount: 2900, currency: "USD", status: "succeeded" },
            { date: "2026-10-01T09:00:00Z", amount: 2900, currency: "USD", status: "failed" },
          ],
        }),
      ),
    );
    render(<BillingPanel />);
    const rows = await screen.findAllByTestId("billing-row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("$29.00")).toBeInTheDocument();
    expect(within(rows[0]).getByText("USD")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Paid")).toBeInTheDocument();
    expect(within(rows[0]).getByText(formatDate("2026-10-02T09:00:00Z"))).toBeInTheDocument();
    expect(within(rows[1]).getByText("Failed")).toBeInTheDocument();
  });

  it("shows Stripe as available and PayPal as disabled with an announced label; clicking does nothing (AC11.6.2)", async () => {
    const requests = mockFetch(
      route("GET", "/settings/billing", () => jsonResponse(200, { payments: [] })),
    );
    render(<BillingPanel />);
    expect(await screen.findByTestId("billing-empty")).toBeInTheDocument();
    expect(screen.getByTestId("payment-option-stripe")).toHaveTextContent("Available");

    const paypal = screen.getByTestId("payment-option-paypal");
    expect(paypal).toHaveAttribute("aria-disabled", "true");
    expect(paypal).toHaveAccessibleDescription("Not available");
    const before = requests.length;
    await userEvent.setup().click(paypal);
    expect(requests).toHaveLength(before);
  });

  it("says when the payments cannot be loaded and tries again", async () => {
    let fail = true;
    mockFetch(
      route("GET", "/settings/billing", () =>
        fail ? errorResponse(500, "INTERNAL_ERROR") : jsonResponse(200, { payments: [] }),
      ),
    );
    render(<BillingPanel />);
    expect(await screen.findByRole("alert")).toHaveTextContent("couldn't load your payments");
    fail = false;
    await userEvent.setup().click(screen.getByTestId("billing-retry-button"));
    expect(await screen.findByTestId("billing-empty")).toBeInTheDocument();
  });
});

describe("format helpers", () => {
  it("writes dates in words and keeps unknown values readable", () => {
    expect(formatDate("2026-10-01T10:00:00Z", "en-GB")).toBe("1 October 2026");
    expect(formatDate("not a date")).toBe("not a date");
    expect(statusText("succeeded")).toBe("Paid");
    expect(statusText("pending")).toBe("Pending");
    expect(statusText("refunded")).toBe("refunded");
  });
});
