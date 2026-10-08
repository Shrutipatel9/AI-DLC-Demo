"use client";

// Settings -> Account Info (US11.4): name, email, verification status and member-since date.
// The full name has no edit control (AC11.4.2).
import { Button } from "@/components/ui/button";
import { useAccountInfo } from "@/lib/settings";

import { formatDate } from "./format";

export function AccountInfoPanel() {
  const account = useAccountInfo();

  if (account.phase === "loading") {
    return (
      <p role="status" className="text-base text-muted" data-testid="account-loading">
        Loading your account…
      </p>
    );
  }
  if (account.phase === "error" || !account.data) {
    return (
      <div className="space-y-4" data-testid="account-error">
        <p role="alert" className="text-base text-heading">
          We couldn&apos;t load your account details. Please try again.
        </p>
        <Button onClick={account.reload} data-testid="account-retry-button">
          Try again
        </Button>
      </div>
    );
  }
  const info = account.data;
  return (
    <dl className="grid gap-4 sm:grid-cols-[10rem_1fr]" data-testid="account-info">
      <dt className="text-sm font-medium text-muted">Full name</dt>
      <dd className="text-base text-heading" data-testid="account-name">
        {info.fullName}
      </dd>
      <dt className="text-sm font-medium text-muted">Email</dt>
      <dd className="break-all text-base text-heading" data-testid="account-email">
        {info.email}
      </dd>
      <dt className="text-sm font-medium text-muted">Verification</dt>
      <dd className="text-base text-heading" data-testid="account-verified">
        {info.isVerified ? "Verified" : "Not verified"}
      </dd>
      <dt className="text-sm font-medium text-muted">Member since</dt>
      <dd className="text-base text-heading" data-testid="account-member-since">
        {formatDate(info.memberSince)}
      </dd>
    </dl>
  );
}
