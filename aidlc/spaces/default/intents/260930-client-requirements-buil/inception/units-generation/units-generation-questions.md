# Units Generation — Questions

This stage groups the 15 components from Domain Design into **units of work** — the phases the build is split into — and maps every story to a unit. It records only what depends on what; the order in which units are actually built (and why) is decided next, in Delivery Planning.

Already settled: the team always builds a thin end-to-end slice first (team practices, walking skeleton: sign-up → emailed code → login → "who am I" across Next.js, FastAPI and PostgreSQL, with CI), so the first unit is that slice.

Pick one letter per question (or X and describe your own answer).

---

### Question 1 — How units are cut
A. Vertical feature slices: each unit delivers its backend component(s) **and** its screens, so every unit can be demonstrated in the browser; the first unit is the thin end-to-end slice (Recommended)
B. By layer: backend units first, then separate frontend units
X. Other (please specify)

[Answer]: A

### Question 2 — How many units
A. About 10 units, each a coherent phase: (1) thin slice + project groundwork, (2) full sign-in and session security, (3) consent and questionnaire, (4) photos and the same-person check, (5) payment, (6) analysis core — pipeline, measurements, report text, (7) AI images, (8) report, Home dashboard and PDF, (9) AI Beauty Assistant, (10) settings and app-wide polish (Recommended)
B. About 5 larger units (auth; onboarding + photos; payment + analysis; report + images; chat + settings)
X. Other (please specify)

[Answer]: A

### Question 3 — What gets deployed
Hosting is undecided, but the shape of the deployables affects how units are built.

A. Two applications, as the client requires: the Next.js frontend, and one FastAPI backend organised as a modular monolith (one codebase with the 13 backend components as modules) that runs as a web process plus a background worker process for analysis (Recommended)
B. Separate services per backend component (microservices)
X. Other (please specify)

[Answer]: A

### Question 4 — How backend components talk to each other
A. Inside the backend, through each module's public Python interface (in-process calls, no internal HTTP or message broker); the frontend talks to the backend over HTTP/JSON (Recommended)
B. Internal HTTP APIs between backend modules
X. Other (please specify)

[Answer]: A

### Question 5 — Working on independent units
After the thin slice, some units don't depend on each other (for example the questionnaire and the photo checks).

A. Record them as independent in the dependency map so they can be built in either order or in parallel; Delivery Planning picks the actual order (Recommended)
B. Force a single straight-line order now
X. Other (please specify)

[Answer]: A
