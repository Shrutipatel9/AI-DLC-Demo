"use client";

// The Settings frame (US11.4-US11.6): a heading and the three sections as links, so each
// section is its own page and the current one is announced (`aria-current`).
import Link from "next/link";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app/app-shell";
import { ProtectedRoute } from "@/components/app/protected-route";
import { Card } from "@/components/ui/card";

export const SETTINGS_SECTIONS = [
  { href: "/settings", label: "Account Info", testId: "settings-tab-account" },
  {
    href: "/settings/password",
    label: "Password",
    testId: "settings-tab-password",
  },
  { href: "/settings/billing", label: "Billing", testId: "settings-tab-billing" },
] as const;

export function SettingsNav({ current }: { current: string }) {
  return (
    <nav aria-label="Settings sections">
      <ul className="flex flex-wrap gap-2 md:flex-col md:gap-1">
        {SETTINGS_SECTIONS.map((section) => (
          <li key={section.href}>
            <Link
              href={section.href}
              aria-current={section.href === current ? "page" : undefined}
              className={`flex min-h-11 items-center gap-2.5 rounded-ui border px-4 text-[15px] font-semibold transition-colors ${
                section.href === current
                  ? "border-accent-soft-border bg-accent-soft text-accent-deep"
                  : "border-transparent text-subheading hover:bg-white hover:text-heading"
              }`}
              data-testid={section.testId}
            >
              {section.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function SettingsPage({
  current,
  title,
  children,
}: {
  current: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <ProtectedRoute>
      <AppShell>
        <div className="mx-auto max-w-[960px]">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-heading">Settings</h1>
            <p className="mt-2 text-lg text-subheading">
              Manage your account, password and payments.
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-[220px_1fr]">
            <SettingsNav current={current} />
            <Card>
              <h2 className="mb-6 text-xl font-bold text-heading">{title}</h2>
              {children}
            </Card>
          </div>
        </div>
      </AppShell>
    </ProtectedRoute>
  );
}
