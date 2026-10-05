"use client";

import type { ReactNode } from "react";

import { useAuth } from "@/lib/auth";

import { AppHeader } from "./app-header";

// Signed-in layout: header with the user menu, then the page (used inside ProtectedRoute).
export function AppShell({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return (
    <div className="flex min-h-screen flex-col">
      <AppHeader userName={user?.fullName ?? ""} />
      <main id="main" className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-10">
        {children}
      </main>
    </div>
  );
}
