"use client";

import { Toaster } from "sonner";

// The single toast region (BR7.1, BR7.5; interaction-spec §2). Top right on wide screens;
// on phones it sits below the header (offset), so it never covers the header navigation.
// At most three toasts are visible. Content, roles and timing come from
// components/feedback/toast.
const HEADER_CLEARANCE = 72;

export function AppToaster() {
  return (
    <div data-testid="toast-region">
      <Toaster
        position="top-right"
        visibleToasts={3}
        offset={{ top: HEADER_CLEARANCE, right: 16 }}
        mobileOffset={{ top: HEADER_CLEARANCE, left: 16, right: 16 }}
        toastOptions={{ unstyled: true }}
      />
    </div>
  );
}
