// Shared confirmation dialog (US11.7; AC11.7.3; BR3.2, BR7.3; NFR9.9 dialog clauses).
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { confirm } from "./confirm";
import { ConfirmDialogHost } from "./confirm-dialog";

const LOGOUT = {
  title: "Log out?",
  body: "You'll need to log in again.",
  confirmLabel: "Log out",
};

function setup() {
  render(
    <>
      <button type="button" data-testid="opener">
        Open
      </button>
      <ConfirmDialogHost />
    </>,
  );
  const opener = screen.getByTestId("opener");
  opener.focus();
  let answer!: Promise<boolean>;
  act(() => {
    answer = confirm(LOGOUT);
  });
  return { opener, answer };
}

describe("confirm dialog", () => {
  it("opens with the title, body and a confirm button that names the action; Cancel has focus", () => {
    setup();
    const dialog = screen.getByTestId("confirm-dialog");
    expect(dialog).toHaveAttribute("role", "alertdialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleName("Log out?");
    expect(dialog).toHaveAccessibleDescription("You'll need to log in again.");
    expect(screen.getByTestId("confirm-dialog-confirm")).toHaveTextContent("Log out");
    expect(screen.getByTestId("confirm-dialog-cancel")).toHaveFocus();
  });

  it("traps Tab and Shift+Tab inside the dialog", async () => {
    setup();
    const user = userEvent.setup();
    const cancel = screen.getByTestId("confirm-dialog-cancel");
    const ok = screen.getByTestId("confirm-dialog-confirm");
    await user.tab();
    expect(ok).toHaveFocus();
    await user.tab();
    expect(cancel).toHaveFocus();
    await user.tab({ shift: true });
    expect(ok).toHaveFocus();
  });

  it("Escape cancels and focus returns to the opener", async () => {
    const { opener, answer } = setup();
    await userEvent.setup().keyboard("{Escape}");
    await expect(answer).resolves.toBe(false);
    expect(screen.queryByTestId("confirm-dialog")).toBeNull();
    expect(opener).toHaveFocus();
  });

  it("the named button confirms; Cancel declines", async () => {
    const first = setup();
    const user = userEvent.setup();
    await user.click(screen.getByTestId("confirm-dialog-confirm"));
    await expect(first.answer).resolves.toBe(true);
    let second!: Promise<boolean>;
    act(() => {
      second = confirm(LOGOUT);
    });
    await user.click(screen.getByTestId("confirm-dialog-cancel"));
    await expect(second).resolves.toBe(false);
  });

  it("refuses a generic confirm label", () => {
    for (const label of ["OK", "yes", " Confirm ", ""]) {
      expect(() => confirm({ ...LOGOUT, confirmLabel: label })).toThrow(/names the action/);
    }
  });

  it("a newer request replaces an open one, which resolves to false", async () => {
    const { answer } = setup();
    let newer!: Promise<boolean>;
    act(() => {
      newer = confirm({ ...LOGOUT, title: "Delete photo?", confirmLabel: "Delete photo" });
    });
    await expect(answer).resolves.toBe(false);
    expect(screen.getByTestId("confirm-dialog")).toHaveAccessibleName("Delete photo?");
    await userEvent.setup().click(screen.getByTestId("confirm-dialog-confirm"));
    await expect(newer).resolves.toBe(true);
  });
});
