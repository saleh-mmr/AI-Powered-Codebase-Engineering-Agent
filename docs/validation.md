# Milestone 1 validation

Status: implemented; local non-Docker checks passed; full acceptance remains pending.

Verified in the authoring environment:

- Backend Ruff lint and formatting pass.
- Backend strict mypy passes for 12 application modules.
- Backend pytest: 7 passed, 1 real-database test intentionally skipped.
- Frontend TypeScript, ESLint, and Prettier pass.
- Frontend Vitest: 4 tests pass (success, 503/retry, malformed response, network failure).
- Vite production build succeeds.
- FastAPI starts with explicit settings and shuts down cleanly.
- Real HTTP liveness returns 200 without a database.
- Real HTTP readiness returns a redacted 503 when the database cannot be reached.
- Running Vite serves the HTML entry point and proxies `/api/health/ready` to the
  real FastAPI service; the database-unavailable response traverses the proxy.
- Alembic offline SQL generation succeeds and includes extension creation and
  version tracking.
- Compose YAML parses; this is not equivalent to Docker Compose runtime validation.

Not verified here:

- Docker images build and all Compose services start.
- Migration applies successfully to a real PostgreSQL/pgvector instance.
- Real readiness succeeds and recovers after a database restart.
- Browser-rendered desktop/mobile layout and accessibility behavior. Chromium was
  unavailable and its attempted download returned an invalid archive. DOM component
  tests passed, but they do not replace a real browser review.
- GitHub Actions execution. The workflow exists; it has not run on GitHub.

Run the README's Docker setup, readiness, failure/recovery, and database-integration
commands before calling Milestone 1 complete. Inspect the page at desktop width and
at a narrow mobile width, keyboard-tab to Check connection, and confirm visible focus.

Known warnings:

- The resolved Starlette test client warns that its httpx integration is deprecated
  in favor of httpx2. The existing integration still passes. Evaluate migration
  alongside upstream test-client updates; do not suppress the warning globally.
- Starlette also uses a deprecated AnyIO BlockingPortal alias. This is upstream
  compatibility debt, not an application failure; track a compatible update.

No paid model APIs are used. No application secrets or imported repositories exist
in this milestone. This record distinguishes test doubles from live dependencies.
