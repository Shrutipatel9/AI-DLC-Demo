"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { UserMenu } from "./user-menu";
// App shell header (US3.8 AC3.8.1; US11.2): the wordmark, Home, Report, AI Visuals and Chat (the
// Beauty Assistant), and the user menu (Settings, Change password, Log out).
// On a phone the four links sit behind one "Menu" button, so each is one extra tap away
// (AC11.2.2); from the tablet width up they are always visible.
export const NAV_LINKS = [
  { href: "/home", label: "Home", testId: "nav-home" },
  { href: "/report", label: "Report", testId: "nav-report" },
  { href: "/visuals", label: "AI Visuals", testId: "nav-visuals" },
  { href: "/chat", label: "Chat", testId: "nav-chat" },
] as const;

export function AppHeader({ userName }: { userName: string }) {
  const [open, setOpen] = useState(false);
  return (
    <header className="border-b border-card-border bg-white">
      <nav
        aria-label="Main"
        className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3"
      >
        <Link
          href="/home"
          className="text-lg font-bold text-heading"
          data-testid="header-wordmark-link"
        >
          <span aria-hidden="true">◆ </span>AI Facial Analysis
        </Link>
        <ul
          id="main-nav-links"
          className={`order-last w-full flex-col gap-1 md:order-none md:flex md:w-auto md:flex-row md:gap-2 ${open ? "flex" : "hidden"}`}
          data-testid="main-nav-links"
        >
          {NAV_LINKS.map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                onClick={() => setOpen(false)}
                className="flex min-h-11 items-center rounded-[var(--radius)] px-3 text-base font-medium text-heading hover:bg-[#eef2f5]"
                data-testid={link.testId}
              >
                {link.label}
              </Link>
            </li>
          ))}
        </ul>
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-expanded={open}
            aria-controls="main-nav-links"
            onClick={() => setOpen((value) => !value)}
            className="inline-flex min-h-11 items-center gap-2 rounded-[var(--radius)] border border-card-border bg-white px-3 text-base font-medium text-heading hover:bg-[#eef2f5] md:hidden"
            data-testid="nav-menu-button"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
            Menu
          </button>
          <UserMenu userName={userName} />
        </div>
      </nav>
    </header>
  );
}
