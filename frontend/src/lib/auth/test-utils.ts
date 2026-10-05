// Deterministic in-memory stand-ins for `navigator.locks` and `BroadcastChannel`, shared by
// simulated tabs in the coordinator and store tests (unit-test instructions: fakeLocks /
// fakeBroadcast). Each can be left out to test the fallback paths. Test-only module.
import type { ChannelLike, LockManagerLike } from "./refresh-coordinator";

export interface FakeLocks extends LockManagerLike {
  /** Names currently held. */
  held(): string[];
}

/** An exclusive lock manager: callbacks for one name run strictly one after another. */
export function fakeLocks(): FakeLocks {
  const tails = new Map<string, Promise<unknown>>();
  const holding = new Set<string>();
  return {
    request<T>(name: string, _options: { mode: "exclusive" }, callback: () => Promise<T>) {
      const previous = tails.get(name) ?? Promise.resolve();
      const run = previous.then(async () => {
        holding.add(name);
        try {
          return await callback();
        } finally {
          holding.delete(name);
        }
      });
      tails.set(
        name,
        run.then(
          () => undefined,
          () => undefined,
        ),
      );
      return run;
    },
    held: () => [...holding],
  };
}

export interface FakeBroadcastHub {
  open(name: string): ChannelLike;
  /** Every message posted on any channel, in order (for assertions). */
  readonly posted: unknown[];
}

/** Same-origin channels: a message reaches every other open channel of the same name. */
export function fakeBroadcast(): FakeBroadcastHub {
  const channels = new Set<FakeChannel>();
  const posted: unknown[] = [];

  class FakeChannel implements ChannelLike {
    private listeners: Array<(event: MessageEvent) => void> = [];
    private closed = false;

    constructor(readonly name: string) {
      channels.add(this);
    }

    postMessage(message: unknown): void {
      if (this.closed) return;
      posted.push(message);
      const copy = structuredClone(message);
      for (const other of channels) {
        if (other !== this && other.name === this.name) {
          void Promise.resolve().then(() => other.deliver(copy));
        }
      }
    }

    addEventListener(_type: "message", listener: (event: MessageEvent) => void): void {
      this.listeners.push(listener);
    }

    close(): void {
      this.closed = true;
      channels.delete(this);
    }

    private deliver(data: unknown): void {
      if (this.closed) return;
      for (const listener of this.listeners) listener({ data } as MessageEvent);
    }
  }

  return { open: (name) => new FakeChannel(name), posted };
}
