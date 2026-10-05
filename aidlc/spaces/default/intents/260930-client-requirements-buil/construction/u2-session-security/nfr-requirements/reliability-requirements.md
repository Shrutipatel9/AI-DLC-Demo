# Reliability Requirements — U2 Session Security

**Sources:** `requirements.md` NFR5 (reliability, errors surfaced), FR3.5 / `FE-006` (never sign out on network errors), functional design WF-U2-2 to WF-U2-4 and the post-review changes R-04 and R-07.

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR5.1 | **Network errors and 5xx never sign the user out.** On restore, the app stays `initializing` with a Retry message. On refresh, waiting requests reject with an error toast and the user stays signed in (BR6.5). | Vitest tests with fetch failures and 500s; Playwright with the API stopped mid-session. |
| NFR5.2 | **Lost refresh response:** after a network error or 5xx on refresh, the client retries once with the same `X-Refresh-Attempt` id, which recovers through NFR2.3 (post-review R-04). | Integration test: the server commits the rotation, the response is dropped, and the retry succeeds. |
| NFR5.3 | **Refresh timeout:** each refresh fetch times out after 10 s, so the cross-tab lock is always released (R-07). | Vitest fake-timer test: a hung fetch releases the lock at 10 s. |
| NFR5.4 | **Single-flight guarantees:** any number of concurrent 401s, plus a proactive refresh, produce exactly one refresh call per tab, and across tabs while the lock is held. Every waiting request is retried at most once (BR6.3, BR6.4). | Test-first Vitest suite: 3 concurrent 401s → 1 call; retry-once; no refresh loop on a refresh 401. |
| NFR5.5 | **Clear exactly once:** a refresh 401 clears the store once and navigates once, whatever the number of waiters (BR6.5). | Vitest: 5 waiters → one `clear` and one `navigate`. |
| NFR5.6 | **Email after response:** on the non-revealing endpoints, sending runs after the response, with the U1 retry and 25 s budget. A final failure is logged at ERROR (`vendor.failed`), and the user can resend (R-01). | Test: an email-fake failure still gives 202 and logs an ERROR. |
| NFR5.7 | **Transactions:** reset (password + token + revocations) and change (password + revocations) are each one transaction, and a failure leaves no partial state (BR4.6, BR5.3). | Injected database failure test. |
| NFR5.8 | **Fallback without Web Locks:** BroadcastChannel claim-and-wait. Without both, per-tab refresh (ADR-006 accepted risk). | Vitest with `navigator.locks` removed; with both removed. |
