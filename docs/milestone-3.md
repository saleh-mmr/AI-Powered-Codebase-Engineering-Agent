# Milestone 3 — Public repositories and background imports

This milestone adds an end-to-end public-repository import experience. You can add
a GitHub URL, watch job stages, browse accepted text files, cancel/retry imports,
and remove a repository. It does not yet parse ASTs, create embeddings, or answer
questions. Imported does not mean indexed.

## Upgrade from Milestone 2

Keep your existing `.env` and PostgreSQL volume. Extract the Milestone 3 archive
separately, then copy `UPGRADE_FROM_MILESTONE_2.patch` into your existing project root.
From that existing `repopilot-ai` root:

```bash
git apply --check UPGRADE_FROM_MILESTONE_2.patch
git apply UPGRADE_FROM_MILESTONE_2.patch
```

The check must finish without errors. If you changed baseline files and it fails,
inspect the conflicts before applying; do not force an overwrite. Complete final
files are also in the archive. Existing account data and `.env` are not touched by
the patch. Add these root `.env` values if absent:

```dotenv
APP_REDIS_URL=redis://redis:6379/0
APP_IMPORT_DOWNLOAD_BYTES=10485760
APP_IMPORT_TIMEOUT_SECONDS=90
```

From the project root:

```bash
docker compose build backend migrate worker dispatcher frontend
docker compose up -d postgres redis
docker compose run --rm migrate alembic upgrade head
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic check
docker compose up -d backend worker dispatcher frontend
docker compose ps -a
```

Expected: `0003_repository_imports (head)`, no model/migration drift, healthy
PostgreSQL/Redis/backend, and running worker, dispatcher, and frontend. The migration
adds three tables: repositories, import_jobs, repository_files. It does not recreate
users/sessions or remove existing accounts. Downgrading 0003 deletes import data;
do not use downgrade as a troubleshooting shortcut.

## First real import

1. Open http://localhost:3000 and sign in.
2. Add the HTTPS root URL of a small public GitHub repository. Python repositories
   are the intended next indexing target; this import stage can display other
   supported UTF-8 source and documentation files too.
3. Expect queued → running → completed (the UI labels completion Imported).
4. Stages include metadata, downloading, validating, storing. These are stages,
   not invented percentage estimates. The UI also shows attempts and file counts.
5. Click Browse files, select a file, and check its content and pinned commit SHA.
6. Refresh the browser: the repository and its files should remain available.

No GitHub or model key is required. GitHub's unauthenticated limits apply. Start
with a small repository under the documented limits rather than a large framework.

## Failure and security acceptance

- Submit a non-GitHub URL: expect 422; no network request is queued.
- Submit the same repository twice: expect 409.
- Submit an inaccessible/private/deleted repository: expect a useful failed-job message.
- Sign into a different account: its list should not show the first user's resources.
  API tests verify that guessing IDs also fails for all actions and file reads.
- Stop the worker, submit an import, and confirm it remains queued. Restart the
  worker and confirm that processing resumes:

```bash
# Project root
docker compose stop worker
# Submit a repository in the browser now.
docker compose start worker
```

- Cancel an active import: expect cancelled, with no partial files published.
  Retry it: expect a new queued job. Cancellation can leave an already-started
  network request running briefly, but the old worker loses publication rights.
- For process-loss recovery, kill/restart a worker during a running import. An
  abandoned claim is eligible again after three minutes. After three lost attempts,
  the job fails rather than looping forever.
- Remove a repository and verify that it disappears. Its import allowance is not reset.
- Stop Redis: auth/import submissions should fail clearly, not bypass rate limits.
  Start Redis again; previously committed queued jobs remain recoverable.

Inspect logs from the project root:

```bash
docker compose logs --tail=100 backend worker dispatcher
```

Logs identify job IDs and safe error codes, without printing source contents or tokens.

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

From `repopilot-ai/frontend`:

```bash
pnpm install --frozen-lockfile
pnpm check
pnpm test
pnpm build
```

Default tests do not require Docker, GitHub, or paid providers. Integration tests
are skipped until explicitly enabled; see docs/validation.md for actual results.

## PostgreSQL, Redis, and Celery integration tests

Use a dedicated database ending in `_test`, not your application's data. With
Compose PostgreSQL and Redis running, create the test DB once from the project root:

```bash
docker compose exec postgres sh -c 'createdb -U "$POSTGRES_USER" repopilot_test'
```

If it already exists, keep it; do not delete a database to rerun tests. In Bash,
from the project root:

```bash
set -a
. ./.env
set +a
export APP_DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/repopilot_test"
export APP_REDIS_URL=redis://127.0.0.1:6379/1
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run alembic check
RUN_DB_TESTS=1 RUN_QUEUE_TESTS=1 uv run pytest -m integration
```

This assumes the URL-safe credentials recommended in the setup guide. Redis DB 1
separates the test queue/counters from the application's DB 0. The worker test uses
an additional unique queue. It delivers a real Celery task through Redis, stores a
controlled source fixture in PostgreSQL, and cleans up its test account. It does
not call GitHub. CI supplies its own PostgreSQL/Redis services and runs these gates.

## API contracts

All paths below are browser/proxy paths; FastAPI internally omits `/api`.
All writes require the existing session cookie, origin/custom request header, and
CSRF proof. JSON POST bodies require application/json.

| Method/path | Success | Behavior |
| --- | --- | --- |
| GET /api/repositories | 200 | Current user's repositories and current jobs |
| POST /api/repositories | 202 | Persist a repository and queued job; body `{ "url": "https://github.com/owner/repo" }` |
| GET /api/repositories/{id} | 200 | Owner-scoped metadata and progress |
| POST /api/repositories/{id}/cancel | 204 | Invalidate a queued/running claim |
| POST /api/repositories/{id}/retry | 202 | New job for a failed/cancelled import |
| DELETE /api/repositories/{id} | 204 | Remove owned repository, jobs, and files |
| GET /api/repositories/{id}/files?offset=0&limit=100 | 200 | Page of file metadata with next_offset |
| GET /api/repositories/{id}/files/{file_id} | 200 | Bounded text content and commit SHA |

Common errors: 401 session expired, 403 CSRF, 404 absent/foreign resource, 409 duplicate
or invalid state, 422 malformed input, 429 quota, 503 database/Redis unavailable.
There is intentionally no unscoped job-ID endpoint. Every job is reached through
its owned repository. File IDs are also scoped to that repository/current import.

## Limits and troubleshooting

- **Queued indefinitely:** verify dispatcher and worker are running, Redis is reachable,
  and all services use the same database and Redis URL. No schema change is needed.
- **Redis unavailable after upgrading:** add APP_REDIS_URL and start Redis. Authentication
  now requires shared rate-limit storage; it no longer falls back to local counters.
- **GitHub rate limited:** wait and retry. No personal token is required or stored.
- **Moved repository:** use the new canonical GitHub URL; redirects are intentionally rejected.
- **Too large/no supported files:** choose a smaller repository. Download defaults to
  10 MiB; expanded archive 40 MiB; retained text 10 MiB; each file 256 KiB; 5,000 entries.
- **Host processes cannot resolve redis/postgres:** replace container hostnames with
  127.0.0.1 in those processes' environment. Compose uses container hostnames.
- **Imported files look old:** they intentionally show the pinned commit, not a live
  branch. Refresh/reindex is a later indexing feature.
- **UI unchanged:** rebuild/restart frontend. Do not remove PostgreSQL volumes.

## Engineering choices and next step

ADR 0003 explains why archives replace cloning, how the durable outbox/lease model
works, why Redis throttling fails closed, and how source isolation is enforced.
The worker reads untrusted text; it is not a sandbox for executing untrusted code.
Zod validates nested API data at runtime in addition to TypeScript's compile-time checks.

Next: Python AST extraction, symbols, chunking, and an inspectable indexing pipeline.
Postponed: embeddings, retrieval, citations, AI chat, private access, history, refresh
of successful imports, and executable repository sandboxes.

Suggested commit: `feat(repositories): add owned public imports and background jobs`
