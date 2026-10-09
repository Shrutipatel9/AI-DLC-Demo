"use client";

// Settings -> Account Info (US11.4): name, email, verification status and member-since date.
// The full name has no edit control (AC11.4.2).
import type { ReactNode } from "react";
import { BadgeCheck, CalendarDays, CircleAlert, Mail, UserRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/page-header";
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
    <dl className="divide-y divide-card-border" data-testid="account-info">
      <Row icon={<UserRound />} label="Full name">
        <dd className="text-base font-medium text-heading" data-testid="account-name">
          {info.fullName}
        </dd>
      </Row>
      <Row icon={<Mail />} label="Email">
        <dd className="break-all text-base font-medium text-heading" data-testid="account-email">
          {info.email}
        </dd>
      </Row>
      <Row icon={<BadgeCheck />} label="Verification">
        <dd data-testid="account-verified">
          {info.isVerified ? (
            <Badge tone="success">
              <BadgeCheck aria-hidden="true" />
              Verified
            </Badge>
          ) : (
            <Badge tone="warning">
              <CircleAlert aria-hidden="true" />
              Not verified
            </Badge>
          )}
        </dd>
      </Row>
      <Row icon={<CalendarDays />} label="Member since">
        <dd className="text-base font-medium text-heading" data-testid="account-member-since">
          {formatDate(info.memberSince)}
        </dd>
      </Row>
    </dl>
  );
}

/** One label/value row with a leading icon. */
function Row({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 py-4 first:pt-0 last:pb-0 sm:grid-cols-[12rem_1fr] sm:items-center">
      <dt className="flex items-center gap-2.5 text-[15px] font-medium text-subheading [&_svg]:size-[18px] [&_svg]:text-accent-strong">
        <span aria-hidden="true">{icon}</span>
        {label}
      </dt>
      {children}
    </div>
  );
}
