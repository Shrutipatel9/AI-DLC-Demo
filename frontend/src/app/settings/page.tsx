import type { Metadata } from "next";

import { AccountInfoPanel } from "@/components/settings/account-info";
import { SettingsPage } from "@/components/settings/settings-shell";

export const metadata: Metadata = { title: "Settings · AI Facial Analysis" };

// Settings -> Account Info (US11.4).
export default function SettingsAccountPage() {
  return (
    <SettingsPage current="/settings" title="Account Info">
      <AccountInfoPanel />
    </SettingsPage>
  );
}
