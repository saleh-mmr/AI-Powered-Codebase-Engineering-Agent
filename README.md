# RepoPilot AI

A repository-understanding application that will grow into a controlled software
engineering agent. **Current scope: Milestone 5, hybrid retrieval and evaluation.**
React/TypeScript/Vite, FastAPI, PostgreSQL/pgvector, Redis, Celery, and a durable
job dispatcher now support authenticated imports, progress, and basic source browsing.
Static indexing, a React source/search inspector, keyword/symbol retrieval and optional
semantic retrieval are now available. Grounded answer generation comes next.

**Upgrading from Milestone 4?** Follow [the Milestone 5 upgrade guide](docs/milestone-5.md).
It preserves your existing `.env`, users, sessions, and PostgreSQL volume.

## Requirements

For the complete local stack: Docker Engine/Desktop with Docker Compose v2.
For host development/checks: Python 3.12, uv 0.12.17, Node.js 24, pnpm 11.19.0.
The lockfiles pin resolved dependencies. No model or GitHub API key is needed for
keyword/symbol search. Semantic search is explicitly opt-in; see docs/milestone-5.md.

## Start the stack

From the extracted project directory:

```bash
cd repopilot-ai
cp .env.example .env
```

Edit `.env`: choose a local password and update both `POSTGRES_PASSWORD` and the
password inside `APP_DATABASE_URL`. Use URL-safe letters and digits for this local
setup. `POSTGRES_USER` and `POSTGRES_DB` must also match the URL. Inside Compose the
hostname is `postgres`. Never commit `.env`.

```bash
docker compose up --build -d
docker compose ps -a
```

Expected: PostgreSQL, Redis, and backend healthy; frontend, worker, and dispatcher running, and `migrate` exited
with code 0. The one-shot migration runs before the backend starts.

Open http://localhost:3000. Create an account with a 15–128 character passphrase. In the protected workspace,
the status card should display **Connected** and **All checks passed**. API docs: http://localhost:8000/docs.

From the project root:

```bash
curl -i http://localhost:8000/health/live
curl -i http://localhost:8000/health/ready
curl -i http://localhost:3000/api/health/ready
docker compose run --rm migrate alembic current
```

Each HTTP call should return 200 and `{"status":"ok","service":"repopilot-api"}`.
The migration should report `0005_hybrid_search (head)`.
The frontend proxy and direct API checks deliberately use different URL prefixes.

## Verify dependency failure and recovery

From the project root, with the stack running:

```bash
docker compose stop postgres
curl -i http://localhost:8000/health/live
curl -i http://localhost:8000/health/ready
```

Liveness stays 200. Readiness returns 503 with `error.code=dependency_unavailable`
and a request ID, without a database URL. Click **Check connection** in the browser:
it should show a useful error. Then:

```bash
docker compose start postgres
```

Wait until PostgreSQL is healthy, then click **Check connection** again. It should
recover. This verifies pool recovery, not just a mocked response.

## Run quality checks locally

From the project root, install backend dependencies and run the checks:

```bash
cd backend
uv sync --frozen
uv run python -m app.embeddings.tokens
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest -m 'not integration'
```

Expected: lint and formatting pass, mypy reports no issues, all unit/API tests pass.
These tests use injectable readiness probes and need no running database.

In a new terminal, from the project root:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm check
pnpm test
pnpm build
```

Expected: TypeScript/ESLint/Prettier pass, component tests pass, and Vite creates
`frontend/dist/`. Build artifacts are ignored by Git.

### Real database integration test

First start the Compose stack and apply the migration as above. From the project
root in a POSIX shell, load the local environment, then replace the container
hostname for access from the host:

```bash
set -a
. ./.env
set +a
export APP_DATABASE_URL="${APP_DATABASE_URL/@postgres:/@127.0.0.1:}"
export APP_REDIS_URL=redis://127.0.0.1:6379/0
cd backend
RUN_DB_TESTS=1 uv run pytest -m integration
```

The URL replacement above requires Bash. For the full isolated integration suite,
including Celery transport, follow docs/milestone-3.md instead of using application data. Expected: the real readiness integration
test passes. Without `RUN_DB_TESTS=1`, it is intentionally skipped. Never run
schema-changing integration tests against a production database.

## Host development with hot reload

Use Compose for PostgreSQL only and run both application processes locally.
From the project root in Bash:

```bash
docker compose up -d postgres redis worker dispatcher
set -a
. ./.env
set +a
export APP_DATABASE_URL="${APP_DATABASE_URL/@postgres:/@127.0.0.1:}"
export APP_REDIS_URL=redis://127.0.0.1:6379/0
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload --port 8000 --no-access-log
```

In another terminal, from the project root:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Open http://localhost:3000. Vite proxies `/api/` to `API_PROXY_TARGET`, whose default
is `http://127.0.0.1:8000`. Stop the Compose frontend/backend first if their ports
are already occupied. The Compose frontend serves a production build; code changes
there require rebuilding the image.

## Configuration

| Variable | Purpose |
| --- | --- |
| POSTGRES_USER | Local database account |
| POSTGRES_PASSWORD | Local database password; do not commit |
| POSTGRES_DB | Database name |
| APP_DATABASE_URL | Required server-only `postgresql+asyncpg` connection URL |
| APP_DATABASE_TIMEOUT_SECONDS | Readiness deadline, default 3 seconds |
| API_PROXY_TARGET | Vite development proxy target; never sent to browser code |
| APP_REDIS_URL | Server-only Redis URL for queue and shared rate limits |
| APP_IMPORT_DOWNLOAD_BYTES | Compressed archive cap; default 10485760 bytes |
| APP_EMBEDDINGS_ENABLED | false by default; opt in to paid semantic search |
| APP_OPENAI_API_KEY | Server-only key, required when embeddings are enabled |
| APP_EMBEDDING_TOKEN_BUDGET | Per-preparation reservation budget, default 200000 |
| APP_EMBEDDING_PRICE_PER_MILLION | Configurable USD estimate, default 0.02 |
| APP_INDEX_TIMEOUT_SECONDS | Static indexing deadline, default 90 seconds (10–120) |
| APP_IMPORT_TIMEOUT_SECONDS | Total import attempt timeout; default 90 seconds |
| APP_ENVIRONMENT | development/test/production; production enforces HTTPS cookies |
| APP_FRONTEND_ORIGIN | Exact browser origin; default http://localhost:3000 |
| APP_COOKIE_SECURE | false for local HTTP; true for HTTPS deployment |
| APP_SESSION_LIFETIME_HOURS | Absolute session lifetime, default 24 hours |
| RUN_DB_TESTS | Explicit opt-in to tests requiring a real migrated database |

Settings are centralized in `backend/app/core/config.py`. Missing or malformed
required settings stop startup. Database unavailability allows process startup,
but readiness returns 503. Backend code does not implicitly source `.env`;
Compose injects it, while host commands explicitly load it.

## Architecture and files

- `frontend/src/app/`: application shell and responsive CSS.
- `frontend/src/features/system/`: health UI and request lifecycle hook.
- `frontend/src/lib/api/client.ts`: typed, runtime-validated health response.
- `frontend/vite.config.ts`: centralized development proxy configuration.
- `frontend/nginx.conf`: static delivery and same-origin API proxy in Compose.
- `backend/app/main.py`: application factory, lifespan, safe request logs.
- `backend/app/core/`: configuration and JSON logging.
- `backend/app/api/routes/health.py`: health endpoint contracts.
- `backend/app/database/session.py`: connection lifecycle and bounded probe.
- `backend/app/schemas/health.py`: typed success/error response schemas.
- `backend/migrations/`: versioned schema operations, no `create_all` startup magic.
- `.github/workflows/ci.yml`: lint, types, tests, real PostgreSQL integration, images.

Read [ADR 0001](docs/decisions/0001-modular-monolith.md) and the
[security model](docs/security.md). Authentication now uses dedicated services, repositories, schemas, and dependencies.
See [ADR 0002](docs/decisions/0002-session-authentication.md). Background imports are now implemented; see [ADR 0003](docs/decisions/0003-public-repository-import.md).
See [ADR 0004](docs/decisions/0004-versioned-static-indexes.md) for the static indexing contracts.
See [ADR 0005](docs/decisions/0005-hybrid-retrieval.md) and [evaluation methodology](docs/evaluation.md).
Retrieval is inspectable independently of future answer generation.

## Migration notes

Revision `0001_enable_pgvector` enables the vector extension and retains it on
downgrade. Revision `0002_users_and_sessions` adds users and hashed sessions,
a unique email constraint, a cascading user foreign key, and session indexes.
The migration account must be allowed to create the extension and application
tables. Revision `0003_repository_imports` adds owned repositories, durable import
jobs, and snapshot files with composite foreign keys and dispatch indexes.
Revision `0004_source_indexes` adds versioned indexes, symbols and chunks with
source/symbol constraints. Downgrading 0004 removes indexes but keeps imports.
Revision `0005_hybrid_search` adds search generations/documents, lexical GIN and
pgvector storage. Downgrading 0005 removes search data but retains source indexes.
Downgrading 0003 deletes import data; downgrading 0002 deletes accounts and sessions; do not use it as a routine
troubleshooting step. ORM metadata and migrations are checked for drift in CI.

## Common errors

- **Port already allocated:** stop the other process using 3000, 8000, or 5432.
- **Missing APP_DATABASE_URL:** use the documented environment-loading commands.
- **Hostname postgres cannot resolve:** that name is for containers; host commands
  must use `127.0.0.1`.
- **Readiness 503:** check `docker compose logs postgres migrate backend`; verify
  migrations with `docker compose run --rm migrate alembic current`.
- **Password authentication failed after editing .env:** existing PostgreSQL volumes
  keep their old password. Restore the matching configuration or explicitly change
  the database role password. Do not delete the volume to fix this casually.
- **pgvector missing or extension permission denied:** use the pgvector image and
  a migration role allowed to provision the extension.
- **Unsupported Node version:** use Node 24 and the pinned pnpm version.
- **First download fails:** verify registry access; retry dependency installation
  without deleting the lockfiles.

Stop without removing database data, from the project root:

```bash
docker compose down
```

## Progress

Implemented: authentication, owned public repositories, bounded archive imports,
Redis/Celery background processing, durable dispatch/recovery, basic source browsing,
shared throttling, versioned Python indexing, symbol/chunk inspection, hybrid retrieval, evaluation tooling, migrations,
Compose, tests, and CI definition. See `docs/validation.md` for actual
verification results and remaining gates.

Next: local retrieval benchmark acceptance, then grounded Q&A. Postponed: email
verification/recovery, OAuth/private repositories, successful-import refresh, local model adapters, learned reranking,
grounded chat, agents, patches, and sandbox execution.

Suggested commit: `feat(retrieval): add hybrid search and reproducible evaluation`
