"use client";

// Header user menu (US3.7, US11.2, US11.5): the name, "Settings", "Change password" and "Log out". Log out asks
// for confirmation in the shared dialog first (BR3.2); cancelling keeps the user signed in
// and returns focus to the menu button.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { confirm } from "@/components/feedback/confirm";
import { toast } from "@/components/feedback/toast";
import { Button } from "@/components/ui/button";
import { useAuthActions } from "@/lib/auth";

const ITEM =
  "block w-full rounded-[var(--radius)] px-3 py-2 text-left text-base hover:bg-[#eef2f5]";

export function UserMenu({ userName }: { userName: string }) {
  const router = useRouter();
  const { logout } = useAuthActions();
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);

  async function onLogOut() {
    setOpen(false);
    buttonRef.current?.focus();
    const confirmed = await confirm({
      title: "Log out?",
      body: "You'll need your password and an emailed code to log in again.",
      confirmLabel: "Log out",
    });
    if (!confirmed) return;
    await logout();
    toast.success("You're logged out.");
    router.replace("/login");
  }

  return (
    <div className="relative">
      <Button
        ref={buttonRef}
        type="button"
        variant="secondary"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls="user-menu"
        onClick={() => setOpen((value) => !value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
        }}
        data-testid="user-menu-button"
      >
        <span data-testid="user-menu-name">{userName}</span>
        <span aria-hidden="true">▾</span>
      </Button>
      {open ? (
        <ul
          id="user-menu"
          role="menu"
          className="absolute right-0 z-10 mt-2 min-w-48 rounded-[var(--radius)] border border-card-border bg-white p-1 shadow-lg"
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setOpen(false);
              buttonRef.current?.focus();
            }
          }}
        >
          <li role="none">
            <Link
              role="menuitem"
              href="/settings"
              className={ITEM}
              onClick={() => setOpen(false)}
              data-testid="user-menu-settings-link"
            >
              Settings
            </Link>
          </li>
          <li role="none">
            <Link
              role="menuitem"
              href="/settings/password"
              className={ITEM}
              onClick={() => setOpen(false)}
              data-testid="user-menu-password-link"
            >
              Change password
            </Link>
          </li>
          <li role="none">
            <button
              type="button"
              role="menuitem"
              className={ITEM}
              onClick={() => void onLogOut()}
              data-testid="user-menu-logout"
            >
              Log out
            </button>
          </li>
        </ul>
      ) : null}
    </div>
  );
}
