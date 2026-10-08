// Header navigation (US11.2: AC11.2.1, AC11.2.2): Home, Report, AI Visuals and Chat in the header,
// Settings in the user menu, and one "Menu" button that reveals the links on a phone.
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppHeader, NAV_LINKS } from "./app-header";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});

describe("The app header", () => {
  it("shows Home, Report, AI Visuals and Chat (AC11.2.1)", () => {
    render(<AppHeader userName="Maya Test" />);
    const nav = screen.getByRole("navigation", { name: "Main" });
    const links = within(screen.getByTestId("main-nav-links")).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual(["Home", "Report", "AI Visuals", "Chat"]);
    expect(links.map((link) => link.getAttribute("href"))).toEqual(
      NAV_LINKS.map((link) => link.href),
    );
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "/home",
      "/report",
      "/visuals",
      "/chat",
    ]);
    expect(nav).toContainElement(screen.getByTestId("user-menu-button"));
  });

  it("puts Settings in the user menu (AC11.2.1)", async () => {
    render(<AppHeader userName="Maya Test" />);
    await userEvent.click(screen.getByTestId("user-menu-button"));
    expect(screen.getByTestId("user-menu-settings-link")).toHaveAttribute("href", "/settings");
    expect(screen.getByTestId("user-menu-settings-link")).toHaveTextContent("Settings");
  });

  it("hides the links behind one Menu button on a phone, so each is one extra tap (AC11.2.2)", async () => {
    render(<AppHeader userName="Maya Test" />);
    const button = screen.getByTestId("nav-menu-button");
    const list = screen.getByTestId("main-nav-links");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveAttribute("aria-controls", "main-nav-links");
    expect(list).toHaveClass("hidden");

    await userEvent.click(button);

    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(list).not.toHaveClass("hidden");
    await userEvent.click(screen.getByTestId("nav-report"));
    expect(list).toHaveClass("hidden");
  });
});
