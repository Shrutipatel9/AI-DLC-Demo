import Link from "next/link";

import { UserMenu } from "./user-menu";

// App shell header with the user menu (US3.8 AC3.8.1; US3.7; interaction-spec §1).
export function AppHeader({ userName }: { userName: string }) {
  return (
    <header className="border-b border-card-border bg-white">
      <nav
        aria-label="Main"
        className="mx-auto flex max-w-[1200px] items-center justify-between px-4 py-3"
      >
        <Link
          href="/home"
          className="text-lg font-bold text-heading"
          data-testid="header-wordmark-link"
        >
          <span aria-hidden="true">◆ </span>AI Facial Analysis
        </Link>
        <UserMenu userName={userName} />
      </nav>
    </header>
  );
}
