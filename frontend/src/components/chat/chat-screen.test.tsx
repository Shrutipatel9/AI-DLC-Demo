// The Beauty Assistant screen (US10.1, US10.3: AC10.1.2-AC10.1.6, AC10.3.1, AC10.3.2).
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { configureApiOrigin } from "@/lib/api/client";
import { errorResponse, jsonResponse, mockFetch, route } from "@/test-utils/fetch-mock";
import { resetNextMocks, toastMock } from "@/test-utils/next-mocks";

import { ChatScreen } from "./chat-screen";

vi.mock("next/navigation", async () => {
  const mocks = await import("@/test-utils/next-mocks");
  return { useRouter: () => mocks.router, useSearchParams: () => mocks.searchParams.value };
});
vi.mock("@/components/feedback/toast", async () => ({
  toast: (await import("@/test-utils/next-mocks")).toastMock,
}));

const RESETS_AT = "2026-10-02T00:00:00Z";

interface Stored {
  role: "user" | "assistant";
  text: string;
  createdAt: string;
}

function state(messages: Stored[] = [], remainingToday = 50) {
  return jsonResponse(200, { messages, remainingToday, resetsAt: RESETS_AT });
}

const at = "2026-10-01T10:00:00Z";

beforeEach(() => {
  resetNextMocks();
  configureApiOrigin("http://api.test");
});

describe("The chat screen", () => {
  it("explains what to ask when there is no conversation yet (AC10.1.5)", async () => {
    mockFetch(route("GET", "/chat/messages", () => state()));
    render(<ChatScreen />);

    const empty = await screen.findByTestId("chat-empty");
    expect(empty).toHaveTextContent("Ask me about your report");
    expect(empty).toHaveTextContent("explain your scores");
    expect(screen.getByTestId("chat-remaining")).toHaveTextContent("50 messages left today");

    await userEvent.click(screen.getByTestId("chat-suggestion-0"));
    expect(screen.getByTestId("chat-input")).toHaveValue("What does my symmetry score mean?");
  });

  it("shows my earlier conversation when I return (AC10.1.2)", async () => {
    mockFetch(
      route("GET", "/chat/messages", () =>
        state(
          [
            { role: "user", text: "Earlier question", createdAt: at },
            { role: "assistant", text: "Earlier answer", createdAt: at },
          ],
          48,
        ),
      ),
    );
    render(<ChatScreen />);

    const log = await screen.findByTestId("chat-log");
    expect(within(log).getByText("Earlier question")).toBeInTheDocument();
    expect(within(log).getByText("Earlier answer")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-empty")).not.toBeInTheDocument();
  });

  it("shows a reply is on its way, then announces the reply without moving focus (AC10.1.3)", async () => {
    let release: (value: Response) => void = () => undefined;
    const requests = mockFetch(
      route("GET", "/chat/messages", () => state()),
      route(
        "POST",
        "/chat/messages",
        () =>
          new Promise<Response>((resolve) => {
            release = resolve;
          }),
      ),
    );
    render(<ChatScreen />);
    const input = await screen.findByTestId("chat-input");
    await userEvent.type(input, "Why is my jaw a priority?");
    await userEvent.click(screen.getByTestId("chat-send-button"));

    expect(await screen.findByTestId("chat-pending")).toHaveTextContent("on its way");
    expect(requests.at(-1)?.body).toEqual({ text: "Why is my jaw a priority?" });
    const log = screen.getByTestId("chat-log");
    expect(log).toHaveAttribute("role", "log");
    expect(log).toHaveAttribute("aria-live", "polite");
    expect(input).toHaveFocus();

    release(
      jsonResponse(200, {
        reply: "Because of its width.",
        remainingToday: 49,
        resetsAt: RESETS_AT,
      }),
    );

    expect(await within(log).findByText("Because of its width.")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-pending")).not.toBeInTheDocument();
    expect(screen.getByTestId("chat-input")).toHaveFocus();
    expect(screen.getByTestId("chat-input")).toHaveValue("");
    expect(screen.getByTestId("chat-remaining")).toHaveTextContent("49 messages left today");
  });

  it("keeps my message and shows an error toast when the assistant fails (AC10.1.4)", async () => {
    mockFetch(
      route("GET", "/chat/messages", () => state()),
      route("POST", "/chat/messages", () => errorResponse(502, "UPSTREAM_UNAVAILABLE")),
    );
    render(<ChatScreen />);
    await userEvent.type(await screen.findByTestId("chat-input"), "Will you answer?");
    await userEvent.click(screen.getByTestId("chat-send-button"));

    expect(await screen.findByTestId("chat-message-failed")).toHaveTextContent("Not answered");
    expect(
      within(screen.getByTestId("chat-log")).getByText("Will you answer?"),
    ).toBeInTheDocument();
    expect(toastMock.error).toHaveBeenCalledWith(expect.stringContaining("Your message is kept"));
    expect(screen.getByTestId("chat-input")).toBeEnabled();
  });

  it("marks an earlier unanswered message after a reload (AC10.1.4)", async () => {
    mockFetch(
      route("GET", "/chat/messages", () =>
        state([{ role: "user", text: "Lost question", createdAt: at }]),
      ),
    );
    render(<ChatScreen />);

    expect(await screen.findByTestId("chat-message-failed")).toBeInTheDocument();
  });

  it("at the limit shows when chat reopens and keeps the draft (AC10.3.1)", async () => {
    mockFetch(
      route("GET", "/chat/messages", () => state([], 1)),
      route("POST", "/chat/messages", () =>
        errorResponse(429, "CHAT_DAILY_LIMIT_REACHED", {
          details: [{ resetsAt: RESETS_AT }],
          headers: { "Retry-After": "3600" },
        }),
      ),
    );
    render(<ChatScreen />);
    await userEvent.type(await screen.findByTestId("chat-input"), "One more");
    await userEvent.click(screen.getByTestId("chat-send-button"));

    const limit = await screen.findByTestId("chat-limit");
    expect(limit).toHaveTextContent("reached today's chat limit");
    expect(limit).toHaveTextContent("Chat reopens");
    expect(screen.queryByTestId("chat-input")).not.toBeInTheDocument();
    expect(screen.getByTestId("chat-remaining")).toHaveTextContent("0 messages left today");
    expect(toastMock.error).toHaveBeenCalled();
    expect(screen.queryByText("One more")).not.toBeInTheDocument();
  });

  it("shows the limit message straight away when no messages are left", async () => {
    mockFetch(route("GET", "/chat/messages", () => state([], 0)));
    render(<ChatScreen />);

    expect(await screen.findByTestId("chat-limit")).toBeInTheDocument();
  });

  it("sends with Enter and keeps Shift+Enter for a new line", async () => {
    const requests = mockFetch(
      route("GET", "/chat/messages", () => state()),
      route("POST", "/chat/messages", () =>
        jsonResponse(200, { reply: "ok", remainingToday: 49, resetsAt: RESETS_AT }),
      ),
    );
    render(<ChatScreen />);
    const input = await screen.findByTestId("chat-input");

    await userEvent.type(input, "line one{Shift>}{Enter}{/Shift}line two");
    expect(input).toHaveValue("line one\nline two");
    await userEvent.type(input, "{Enter}");

    await waitFor(() => expect(requests.at(-1)?.method).toBe("POST"));
    expect(requests.at(-1)?.body).toEqual({ text: "line one\nline two" });
  });

  it("explains that chat opens after the analysis (402 and 404)", async () => {
    mockFetch(route("GET", "/chat/messages", () => errorResponse(404, "REPORT_NOT_READY")));
    render(<ChatScreen />);

    expect(await screen.findByTestId("chat-none")).toHaveTextContent("Chat opens after");
    expect(screen.getByTestId("chat-analysis-link")).toHaveAttribute("href", "/analysis");
  });

  it("offers Try again when the conversation cannot be loaded", async () => {
    let calls = 0;
    mockFetch(
      route("GET", "/chat/messages", () => {
        calls += 1;
        return calls === 1 ? errorResponse(500, "INTERNAL_ERROR") : state();
      }),
    );
    render(<ChatScreen />);

    await userEvent.click(await screen.findByTestId("chat-retry-button"));

    expect(await screen.findByTestId("chat")).toBeInTheDocument();
  });
});
