// Error boundary logs the failing call's request id (NFR5.11, AC1.8.2).
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";

import ErrorPage from "./error";

describe("ErrorPage", () => {
  it("logs and shows the request id of a failed API call", async () => {
    const log = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const reset = vi.fn();
    const error = new ApiError({
      status: 500,
      code: "INTERNAL_ERROR",
      message: "x",
      requestId: "rid-7",
    });
    render(<ErrorPage error={error} reset={reset} />);
    expect(screen.getByTestId("error-request-id")).toHaveTextContent("rid-7");
    expect(log).toHaveBeenCalledWith("Unhandled UI error", {
      requestId: "rid-7",
      name: "ApiError",
    });
    await userEvent.setup().click(screen.getByTestId("error-try-again-button"));
    expect(reset).toHaveBeenCalled();
  });

  it("shows no reference for non-API errors", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(<ErrorPage error={new Error("boom")} reset={vi.fn()} />);
    expect(screen.queryByTestId("error-request-id")).toBeNull();
    expect(screen.getByRole("heading")).toHaveTextContent("Something went wrong");
  });
});
