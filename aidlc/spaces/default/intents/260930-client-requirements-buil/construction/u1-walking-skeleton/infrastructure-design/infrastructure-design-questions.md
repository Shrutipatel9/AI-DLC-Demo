# Infrastructure Design — U1 Walking Skeleton — Questions

There is no hosting in this workflow (team Deployment practice, `NFR-010`). The infrastructure for U1 is therefore the local Docker Compose setup and the GitHub Actions pipeline. Two choices remain open.

Pick one letter per question (or X and describe your own answer).

---

### Question 1 — How the apps run locally and in the end-to-end CI job
A. Compose runs only the supporting services (PostgreSQL, Mailpit). The API and web app run as normal processes (`uv run`, `pnpm`), both on a developer machine and on the CI runner. No Dockerfiles until a host is chosen (Recommended)
B. Add Dockerfiles for the API and the web app now. Compose runs the whole stack, and CI builds the images
X. Other (please specify)

[Answer]: A

### Question 2 — Secrets in CI
U1 needs a JWT signing key and a code-hashing key to run tests. No real outside service is called in CI (email goes to the fake or to Mailpit).

A. Each CI run generates throwaway test keys (`openssl rand`) inside the job. The repository holds no secrets for U1 (Recommended)
B. Store fixed test keys as GitHub repository secrets
X. Other (please specify)

[Answer]: A
