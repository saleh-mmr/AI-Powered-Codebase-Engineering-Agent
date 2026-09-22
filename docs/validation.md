# Validation record

## Milestone 1

The user reported completion after receiving the Docker/database validation
procedure. Those local results were not independently rerun in the authoring
environment. The original baseline had 7 backend and 4 frontend tests passing,
with live API/proxy smoke checks and a successful frontend build.

## Milestone 2

Implemented; PostgreSQL/browser acceptance remains pending on the user's machine
or in CI. Do not treat authored CI configuration as an executed CI result.

Verified here:

- Backend Ruff lint/formatting and strict mypy pass.
- 25 backend tests pass; two PostgreSQL integration tests skip intentionally.
- API auth tests exercise real password hashes, ORM storage, service logic, and
  cookie handling against disposable SQLite databases; no mock auth service.
- Coverage includes registration, duplicate normalized email, cookie flags,
  session rotation, old-cookie replay, expiry, missing/invalid cookie, generic
  login errors, cross-user ID injection, CSRF isolation, origin/custom-header
  checks, validation redaction, JSON-only requests, and login throttling.
- Frontend TypeScript, ESLint, Prettier, nine component tests, and production build pass.
- Frontend tests use controlled HTTP responses; they are not browser E2E tests.
- Alembic offline upgrade SQL generation and revision chain are checked.
- Upgrade patch is checked against the original Milestone 1 source snapshot.

Pending:

- Applying revision 0002 to PostgreSQL and checking ORM/migration drift.
- Running both real PostgreSQL integration tests.
- Building and starting the updated Docker images.
- Browser-based registration/login/refresh/logout, desktop/mobile visual review,
  and keyboard checks. The authoring environment lacks a working Chromium runtime.
- Executing GitHub Actions on the user's repository.

Use docs/milestone-2.md for exact upgrade and acceptance commands.

Known upstream warnings: Starlette's test client deprecates its current httpx
integration and uses a deprecated AnyIO BlockingPortal alias. Tests pass; neither
warning is suppressed. Track compatible upstream updates. No paid API calls occur.
