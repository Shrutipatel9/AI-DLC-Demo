"use client";

import { FileText, House, Menu, MessageCircle, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState, useSyncExternalStore } from "react";

import { Logo } from "@/components/brand/logo";

import { UserMenu } from "./user-menu";
// App shell header (US3.8 AC3.8.1; US11.2): the FaceIQ logo, Home, Report, AI Visuals and Chat
// (the Beauty Assistant), and the user menu (Settings, Change password, Log out).
// On a phone the four links sit behind one "Menu" button, so each is one extra tap away
// (AC11.2.2); from the tablet width up they are always visible.
export const NAV_LINKS = [
  { href: "/home", label: "Home", testId: "nav-home", icon: House },
  { href: "/report", label: "Report", testId: "nav-report", icon: FileText },
  { href: "/visuals", label: "AI Visuals", testId: "nav-visuals", icon: Sparkles },
  { href: "/chat", label: "Chat", testId: "nav-chat", icon: MessageCircle },
] as const;

function subscribeToHistory(onChange: () => void): () => void {
  window.addEventListener("popstate", onChange);
  return () => window.removeEventListener("popstate", onChange);
}

/** The current path (each signed-in page mounts its own shell, so this is read per page). */
function useCurrentPath(): string {
  return useSyncExternalStore(
    subscribeToHistory,
    () => window.location.pathname,
    () => "",
  );
}

export function AppHeader({ userName }: { userName: string }) {
  const [open, setOpen] = useState(false);
  const path = useCurrentPath();
  return (
    <header className="sticky top-0 z-30 border-b border-card-border/80 bg-white/85 backdrop-blur-md">
      <nav
        aria-label="Main"
        className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3"
      >
        <Link
          href="/home"
          aria-label="FaceIQ home"
          className="rounded-lg"
          data-testid="header-wordmark-link"
        >
          <Logo />
        </Link>
        <ul
          id="main-nav-links"
          className={`order-last w-full flex-col gap-1 border-t border-card-border pt-2 md:order-none md:flex md:w-auto md:flex-row md:gap-1 md:border-0 md:pt-0 ${open ? "flex" : "hidden"}`}
          data-testid="main-nav-links"
        >
          {NAV_LINKS.map((link) => {
            const active = path === link.href || path.startsWith(`${link.href}/`);
            const Icon = link.icon;
            return (
              <li key={link.href}>
                <Link
                  href={link.href}
                  onClick={() => setOpen(false)}
                  aria-current={active ? "page" : undefined}
                  className="app-nav-link"
                  data-testid={link.testId}
                >
                  <Icon className="size-[18px]" aria-hidden="true" />
                  {link.label}
                </Link>
              </li>
            );
          })}
        </ul>
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-expanded={open}
            aria-controls="main-nav-links"
            onClick={() => setOpen((value) => !value)}
            className="inline-flex min-h-11 items-center gap-2 rounded-ui border border-card-border bg-white px-3 text-base font-semibold text-heading hover:bg-surface-muted md:hidden"
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
