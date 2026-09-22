# Milestone 2 — Authentication and protected workspace

## Goal and architecture

Introduce a persisted user identity before storing user-owned repositories. React
handles forms and UI state; FastAPI enforces identity and CSRF; services own the
login lifecycle; SQLAlchemy persists users and sessions. This is not a security
boundary implemented solely by hiding UI components.

Review ADR 0002 for password hashing, session rotation, ownership boundaries,
CSRF, indexes, constraints, and the limitations of local throttling.

## Upgrade an existing Milestone 1 checkout

Preserve your existing `.env` and database volume. Do not run `docker compose down -v`.
The archive includes complete final source plus `UPGRADE_FROM_MILESTONE_1.patch`.
Extract it into a separate directory so you can apply the patch to your existing
checkout. With Git installed, from your existing `repopilot-ai` root, use the actual
absolute path to the extracted patch:

```bash
git apply --check /absolute/path/to/extracted/repopilot-ai/UPGRADE_FROM_MILESTONE_1.patch
git apply /absolute/path/to/extracted/repopilot-ai/UPGRADE_FROM_MILESTONE_1.patch
```

Replace the example absolute path with the patch's location. `--check` must finish
without errors before applying. If you edited the baseline files, stop on conflicts
and inspect them; do not force the patch. The complete archive files provide the
final implementation for comparison. Patch application does not edit `.env`.

Add these lines to your existing root `.env` if absent:

```dotenv
APP_ENVIRONMENT=development
APP_FRONTEND_ORIGIN=http://localhost:3000
APP_COOKIE_SECURE=false
APP_SESSION_LIFETIME_HOURS=24
```

The origin must exactly match the browser URL, including port and without a trailing
slash. Keep `APP_COOKIE_SECURE=false` only for this local HTTP development setup.
Production configuration requires an HTTPS origin and Secure cookies.

From your existing project root:

```bash
docker compose build backend migrate frontend
docker compose up -d postgres
docker compose run --rm migrate alembic upgrade head
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic check
docker compose up -d backend frontend
```

Expected: migration reports `0002_users_and_sessions (head)`; Alembic check reports
no new upgrade operations; backend is healthy. Existing PostgreSQL data remains.
The migration adds users and sessions, so no existing application data needs backfill.
Do not downgrade 0002 to troubleshoot: its downgrade deletes accounts and sessions.

## Browser acceptance procedure

Open http://localhost:3000 (use `localhost`, not `127.0.0.1`, with the default origin).

1. Choose Create an account; enter a name, email, and 15–128 character passphrase.
2. Expect the protected welcome workspace and your email, with no repository data yet.
3. Refresh: the workspace stays authenticated through the server-side session.
4. Sign out: return to the sign-in form. Reload: remain signed out.
5. Sign in again with the same credentials. A wrong password should show a generic
   error without entering the workspace.
6. Create a second account in a private browser window. Verify each window shows its
   own account, not the other account.
7. In browser storage tools, verify the session cookie is HttpOnly and SameSite=Lax;
   no token should be in localStorage. Local HTTP intentionally omits Secure.
8. Stop PostgreSQL after signing in, refresh, and expect a recoverable server error
   rather than a silent redirect. Start it and retry the session check.
9. Inspect at mobile width, tab through labeled inputs and buttons, and confirm visible focus.

For a server-side authorization check, from the project root:

```bash
curl -i http://localhost:3000/api/auth/me
curl -i -X POST http://localhost:3000/api/auth/logout \
  -H 'Content-Type: application/json' -d '{}'
```

With no cookie, `/me` returns 401. A write without the required origin/header returns
403. Neither returns credentials. API tests additionally verify expiry, rotation,
CSRF from another session, cookie replay after logout, and injected user IDs.

## Automated checks

From the project root:

```bash
cd backend
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

Expected: 25 tests pass; two PostgreSQL tests skip without RUN_DB_TESTS=1.

In a new terminal from the project root:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm check
pnpm test
pnpm build
```

Expected: all checks pass, nine component tests pass, and dist builds.

For real PostgreSQL tests, after applying migrations, from the project root in Bash:

```bash
set -a
. ./.env
set +a
export APP_DATABASE_URL="${APP_DATABASE_URL/@postgres:/@127.0.0.1:}"
cd backend
RUN_DB_TESTS=1 uv run pytest -m integration
```

Expected: both integration tests pass. The auth integration test creates a unique
test account, exercises registration/login/logout, and deletes it afterward. Use a
local or dedicated test database. CI also runs migrations and checks model drift.

## API contracts

Browser paths include `/api`; FastAPI's internal paths omit it because the proxy
strips the prefix.

| Method and browser path | Request | Success | Important errors |
| --- | --- | --- | --- |
| POST /api/auth/register | name, email, password | 201; user/session metadata; Set-Cookie | 409 duplicate; 422 invalid; 429 throttled |
| POST /api/auth/login | email, password | 200; user/session metadata; rotated Set-Cookie | 401 bad credentials; 429 throttled |
| GET /api/auth/me | Session cookie | 200; current user, CSRF proof, expiry | 401 missing/expired/revoked session |
| POST /api/auth/logout | Cookie, CSRF header, JSON object | 204; session revoked and cookie deleted | 401 unauthenticated; 403 invalid proof |

All writes require `Origin: http://localhost:3000`, `X-RepoPilot-Request: 1`, and
`Content-Type: application/json` in local development. Authenticated writes also
require `X-CSRF-Token` from the current session response. The browser generates
Origin automatically; JavaScript must not attempt to set it.

Example registration body:

```json
{"name":"Saleh","email":"saleh@example.com","password":"a long unique passphrase"}
```

Response fields: `user` (id, email, name, created_at), `csrf_token`, `expires_at`.
The raw session token is only in Set-Cookie. Password hashes and session hashes are
never API response fields. Errors consistently contain `error.code`, `error.message`,
and `error.request_id`. Validation errors intentionally do not echo submitted inputs.

## Common errors

- **403:** browser origin differs from APP_FRONTEND_ORIGIN, custom request header is
  missing, or the CSRF proof belongs to an old session. Reload after another tab signs
  in. Keep the origin exact; Swagger's localhost:8000 origin is not the frontend.
- **401 immediately after login:** Secure cookies enabled on local plain HTTP, cookie
  not sent, or session expired. Do not disable Secure for a real HTTPS deployment.
- **503 mentioning migrations:** apply Alembic revision 0002 and verify database access.
- **409 registration:** that normalized email already exists; use the login form.
- **422 registration:** check email, nonblank name, and passphrase length.
- **429:** wait one minute. A successful registration also consumes an attempt.
- **Old UI:** rebuild the frontend image; Compose serves a static production build.

## Progress and commit

Implemented: persisted users, session lifecycle, CSRF, local throttling, protected
React workspace, API/component tests, and the migration. PostgreSQL and browser
acceptance must pass on the user's machine/CI before this milestone is closed.

Next: public repository import, resource ownership checks, Redis/Celery job states.
Postponed: email verification/recovery, distributed throttling, OAuth, idle timeout,
account editing, all-device logout, and public deployment.

Suggested commit: `feat(auth): add session authentication and protected workspace`
