// Toast service and region (US11.7; AC11.7.1, AC11.7.2, AC11.7.5; BR7.1, BR7.2, BR7.5;
// NFR9.9 toast clauses).
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast as sonner } from "sonner";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppToaster } from "@/components/ui/toaster";

import { SUCCESS_TOAST_MS, toast } from "./toast";

describe("toast service", () => {
  afterEach(() => {
    act(() => {
      sonner.dismiss();
    });
  });

  it("success toasts are polite status messages", async () => {
    render(<AppToaster />);
    act(() => {
      toast.success("Saved.");
    });
    const card = await screen.findByTestId("toast-success");
    expect(card).toHaveAttribute("role", "status");
    expect(card).toHaveAttribute("aria-live", "polite");
    expect(card).toHaveTextContent("Saved.");
  });

  it("error toasts are assertive alerts", async () => {
    render(<AppToaster />);
    act(() => {
      toast.error("That failed.");
    });
    const card = await screen.findByTestId("toast-error");
    expect(card).toHaveAttribute("role", "alert");
    expect(card).toHaveAttribute("aria-live", "assertive");
  });

  it("showing a toast never moves focus", async () => {
    render(
      <>
        <input data-testid="field" />
        <AppToaster />
      </>,
    );
    const field = screen.getByTestId("field");
    field.focus();
    act(() => {
      toast.error("Nope.");
    });
    await screen.findByTestId("toast-error");
    expect(field).toHaveFocus();
  });

  it("each toast can be dismissed with its close button by keyboard", async () => {
    render(<AppToaster />);
    act(() => {
      toast.error("Dismiss me.");
    });
    const card = await screen.findByTestId("toast-error");
    const close = within(card).getByTestId("toast-close-button");
    expect(close).toHaveAccessibleName("Dismiss notification");
    close.focus();
    await userEvent.setup().keyboard("{Enter}");
    await waitFor(() => expect(screen.queryByText("Dismiss me.")).toBeNull());
  });

  it("success toasts last 5 seconds; error toasts stay until dismissed", () => {
    const custom = vi.spyOn(sonner, "custom");
    toast.success("ok");
    toast.error("bad");
    expect(custom.mock.calls[0][1]).toMatchObject({ duration: SUCCESS_TOAST_MS });
    expect(SUCCESS_TOAST_MS).toBe(5_000);
    expect(custom.mock.calls[1][1]).toMatchObject({ duration: Number.POSITIVE_INFINITY });
  });

  it("the region shows at most three toasts and sits below the header", async () => {
    render(<AppToaster />);
    const region = screen.getByTestId("toast-region");
    act(() => {
      for (const n of [1, 2, 3, 4]) toast.success(`Toast ${n}`);
    });
    await screen.findByText("Toast 4");
    const list = region.querySelector("ol");
    expect(list).not.toBeNull();
    const style = list?.getAttribute("style") ?? "";
    expect(style).toContain("--offset-top: 72px");
    expect(style).toContain("--mobile-offset-top: 72px");
    const visible = region.querySelectorAll('[data-sonner-toast][data-visible="true"]');
    expect(visible.length).toBeLessThanOrEqual(3);
  });
});
