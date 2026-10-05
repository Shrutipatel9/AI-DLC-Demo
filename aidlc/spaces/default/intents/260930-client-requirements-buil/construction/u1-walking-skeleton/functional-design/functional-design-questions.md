# Functional Design — U1 Walking Skeleton — Questions

U1 is the thin end-to-end slice: sign up → emailed code → verify → log in → "who am I", plus the project groundwork (stories US1.1–US1.6, US1.8, US1.9, US3.1, US3.2, US3.4, US3.8). Almost everything is already fixed by the requirements, stories and API contracts, so only three gaps remain.

Pick one letter per question (or X and describe your own answer).

---

### Question 1 — Sign-up and login code format
The client fixes a 6-digit code only for password reset (`AUTH-015`); it doesn't say the length for sign-up and login codes.

A. 6 digits for every code (sign-up, login, reset), so users see one consistent format (Recommended)
B. 8 digits for sign-up and login, 6 for reset
X. Other (please specify)

[Answer]: A

### Question 2 — What a signed-in user sees in this first slice
The real Home dashboard arrives in Bolt 8, and "next step" routing in Bolt 10.

A. A simple signed-in placeholder page: the app header with "Hi, {full name}" and the user menu, plus a short "Your journey starts here" note — replaced later (Recommended)
B. Go straight to the consent screen (which isn't built until Bolt 3, so an empty page for now)
X. Other (please specify)

[Answer]: A

### Question 3 — Reloading the page in this first slice
Staying signed in across reloads (refresh cookie + session restore) is Bolt 2. In this first slice the access token lives only in memory, as the client requires.

A. Accept that a page reload signs the user out until Bolt 2 adds session restore; the refresh cookie is already set at login, so Bolt 2 only adds the restore (Recommended)
B. Pull session restore into this slice (makes Bolt 1 bigger)
X. Other (please specify)

[Answer]: A
