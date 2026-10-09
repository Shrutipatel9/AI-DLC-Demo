import type { Metadata } from "next";

import { BillingPanel } from "@/components/settings/billing-panel";
import { SettingsPage } from "@/components/settings/settings-shell";

export const metadata: Metadata = { title: "Billing · FaceIQ" };

// Settings -> Billing (US11.6).
export default function SettingsBillingPage() {
  return (
    <SettingsPage current="/settings/billing" title="Billing">
      <BillingPanel />
    </SettingsPage>
  );
}
