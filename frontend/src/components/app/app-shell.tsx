"use client";

import type { ReactNode } from "react";

import { useAuth } from "@/lib/auth";

import { AppHeader } from "./app-header";

// Signed-in layout: the sticky header with the user menu, the page, and a slim footer
// (used inside ProtectedRoute).
export function AppShell({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return (
    <div className="bg-app-shell flex min-h-screen flex-col">
      <AppHeader userName={user?.fullName ?? ""} />
      <main id="main" className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-8 sm:py-10">
        {children}
      </main>
      <footer className="border-t border-card-border bg-white/70">
        <div className="mx-auto flex max-w-[1200px] flex-col items-center justify-between gap-2 px-4 py-5 text-sm text-muted sm:flex-row">
          <p>© {new Date().getFullYear()} FaceIQ</p>
        </div>
      </footer>
    </div>
  );
}
