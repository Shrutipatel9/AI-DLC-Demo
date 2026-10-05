import Link from "next/link";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";

// Public shell: wordmark header and a 480 px card (mockups §0.1, §2).
export function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-card-border bg-white">
        <nav aria-label="Main" className="mx-auto flex max-w-[1200px] items-center px-4 py-3">
          <Link
            href="/"
            className="text-lg font-bold text-heading"
            data-testid="header-wordmark-link"
          >
            <span aria-hidden="true">◆ </span>AI Facial Analysis
          </Link>
        </nav>
      </header>
      <main id="main" className="mx-auto w-full max-w-[480px] flex-1 px-4 py-10">
        <Card>
          <h1 className="mb-6 text-2xl font-bold text-heading">{title}</h1>
          {children}
        </Card>
      </main>
    </div>
  );
}
