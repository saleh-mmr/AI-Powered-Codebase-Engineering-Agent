# Milestone 4 — Python symbols and inspectable source chunks

This milestone turns an imported commit into a static code index. It is the input
to later retrieval: we can inspect source units and verify provenance before an
LLM or embedding provider is involved. React remains the frontend.

## Architecture and changed files

The browser requests indexing through an authorized FastAPI service. PostgreSQL
stores a queued index generation. The existing dispatcher and Celery worker parse
stored files, publish atomically, and expose status and results back to React.

| Responsibility | Files |
| --- | --- |
| Pure AST parsing and source chunks | backend/app/indexing/parser.py, chunks.py, pipeline.py |
| Offline inspection | backend/app/indexing/inspect.py |
| Models | backend/app/models/repository_index.py, code.py, repository_file.py |
| Migration | backend/migrations/versions/0004_source_indexes.py |
| Background execution | backend/app/jobs/index_repository.py, state.py, dispatcher.py, celery_app.py |
| Authorized API | backend/app/api/routes/indexes.py, schemas/index.py, services/index.py, repositories/index.py |
| React feature | frontend/src/features/indexing/api.ts, useIndex.ts, IndexInspector.tsx, IndexedFileDetails.tsx |
| Browser integration | frontend/src/features/repositories/FileBrowser.tsx, RepositoryWorkspace.tsx |
| Tests | backend/tests/unit/test_indexing.py, tests/api/test_indexes.py, tests/integration/test_worker_roundtrip.py; frontend/tests/indexing.test.tsx |

Paths in the API row after the first are relative to backend/app/. The complete,
exact changed-file list is docs/milestone-4-files.txt; the exact patch is
UPGRADE_FROM_MILESTONE_3.patch. Complete usable final files are in the archive.
ADR 0004 documents the decisions, limits and deviations from the illustrative schema.

## Upgrade from Milestone 3

Keep your existing .env, Git history and database volume. Extract the new archive
separately and copy UPGRADE_FROM_MILESTONE_3.patch into the existing repopilot-ai
root. Run these commands from that existing root:

```bash
git apply --check UPGRADE_FROM_MILESTONE_3.patch
git apply UPGRADE_FROM_MILESTONE_3.patch
```

The check must exit successfully. If you edited baseline files and it fails, inspect
the conflicts; do not force an overwrite. The archive also contains the full files.
The patch is tested against the delivered Milestone 3 baseline.

Optionally add this value to your root .env; Compose supplies the same default:

```dotenv
APP_INDEX_TIMEOUT_SECONDS=90
```

Allowed range: 10–120 seconds. No new credentials, model keys or services are needed.
From the project root:

```bash
docker compose stop backend worker dispatcher frontend
docker compose build backend migrate worker dispatcher frontend
docker compose up -d postgres redis
docker compose run --rm migrate alembic upgrade head
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic check
docker compose up -d backend worker dispatcher frontend
docker compose ps -a
```

Expected: 0004_source_indexes (head), no migration/model drift, healthy PostgreSQL,
Redis and backend, and running frontend, worker and dispatcher. Existing imported
files/users remain. Indexes are built only when requested, not during migration.
For a fresh installation, use README.md's .env setup and docker compose up --build -d.

## Database design

- repository_indexes belongs to an import job and repository through a composite
  foreign key; it records commit/pipeline version, state, lease, counts and diagnostics.
- The partial unique current-generation index prevents competing current attempts.
  A status/available_at index supports dispatch. Completed old generations remain
  available when a new generation fails.
- code_symbols holds lexical relationships and metadata. Per-file ordinals distinguish
  duplicate names; scoped foreign keys validate parent references.
- code_chunks holds exact source slices, source ranges, content hashes and optional
  symbol links. Source/index composite foreign keys reject cross-snapshot records.
- Unique (index_id, file_id, ordinal) indexes support deterministic pagination.
  File-ID indexes support cascading cleanup. Line/offset checks reject invalid ranges.
- Removing a repository cascades through imports, files, indexes, symbols and chunks.
  Downgrading 0004 deletes all index data but retains imported source. Do not use
  downgrade or volume deletion as a troubleshooting shortcut.

## Manual acceptance

1. Open http://localhost:3000, sign in, and open Browse files on an imported small
   Python repository. If needed, import one first using Milestone 3's workflow.
2. In Source index, click Build index. Expect queued → running → completed.
   Stages include starting, parsing and storing; no invented percentage is displayed.
3. Select a .py file. Inspect symbol names, parent-qualified names and source ranges.
   Expand a chunk and compare its content/lines with the original source above.
4. Confirm the displayed commit SHA is the imported SHA. Refresh the browser;
   the completed index and source results should remain available.
5. Click Check index. An unchanged source/pipeline reuses the completed generation;
   it should not create duplicate chunks or call any paid API.
6. Use a repository containing an invalid Python file. Expect a parsing diagnostic
   and fallback chunks; valid files should still have symbols. Non-Python files get
   text chunks. Empty files produce zero chunks.
7. Check narrow-screen layout, keyboard operation of buttons/details, and scrolling
   long source. Source is rendered as React text, including apparent HTML tags.
8. In a separate account, confirm this repository is absent. Automated API tests
   additionally check guessed repository/file IDs and CSRF failures.

Queue/cancellation check: choose an imported repository with no completed index.
From the project root:

```bash
docker compose stop worker
```

Click Build index: it should remain queued. Cancel it: expect cancelled. Click
Build index again, then from the project root:

```bash
docker compose start worker
docker compose logs --tail=100 worker dispatcher backend
```

Expect completion after restart. A cancelled/expired claim cannot publish partial
results. Safe logs include job ID, duration, counts and failure code, not source text.
Abandoned running claims become eligible after 180 seconds, with at most 3 attempts.

## Automated checks

From the project root:

```bash
cd backend
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
uv run python -m app.indexing.inspect tests/fixtures/indexing/sample.py
```

Expected: lint/format/type checks pass; 87 tests pass and 4 infrastructure tests
skip without opt-in. The inspection command prints JSON containing 7 symbols,
signatures/docstrings, source chunks, pipeline version and no diagnostic. It needs
no database, Redis or API key and does not execute the fixture.

In a second terminal, from the project root:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm check
pnpm test
pnpm build
```

Expected: checks pass, 16 component tests pass, production output is created in dist/.
Backend fixtures verify exact source reconstruction, Unicode/CRLF preservation,
byte caps, lexical scopes, explicit fallback, authorization, duplicate delivery,
lease takeover/cancellation, failed-generation preservation and atomic rollback.

For real infrastructure, follow the dedicated repopilot_test database/Redis DB 1
commands in docs/milestone-3.md. Apply migration head before running:

```bash
# repopilot-ai/backend, with APP_DATABASE_URL pointing to repopilot_test
# and APP_REDIS_URL pointing to the isolated test Redis database
uv run alembic upgrade head
uv run alembic check
RUN_DB_TESTS=1 RUN_QUEUE_TESTS=1 uv run pytest -m integration
```

The existing queue test now delivers both import and indexing tasks through Redis,
using real PostgreSQL and a controlled source fixture. CI runs this gate. Do not
point it at application or production data. A defined CI workflow is not proof of
an executed passing run; docs/validation.md records what was actually run here.

## API contracts

Paths below include the browser proxy prefix. FastAPI internally omits /api.
Reads require a session; writes additionally require the Origin/custom request
header and CSRF proof from the existing authentication flow. POST body is {};
unknown fields are rejected. Ownership is checked server-side, never inferred
from a frontend ID.

| Method and path | Success | Contract |
| --- | --- | --- |
| GET /api/repositories/{id}/index | 200 | latest attempt and active completed generation, each nullable |
| POST /api/repositories/{id}/index | 202 or 200 | Queue generation, or return matching completed generation |
| POST /api/repositories/{id}/index/cancel | 204 | Revoke queued/running claim |
| GET /api/repositories/{id}/index/files/{file_id}?symbol_offset=0&chunk_offset=0 | 200 | Commit/path/language, up to 50 symbols and 20 chunks, next offsets |

Errors: 401 expired session, 403 CSRF, 404 absent/foreign resource, 409 incomplete
import/active index/missing completed index, 422 malformed body/offset, 429 index
start limit (5/minute/user), 503 dependency failure. A completed index is required
for indexed-file reads. Ordinary imported-file reads remain available independently.
Open http://localhost:8000/docs for complete generated request/response schemas.

## Important implementation details

Symbols use static Python 3.12 syntax; this is not a type checker or cross-file
semantic resolver. Signatures are normalized metadata. Their exact code is retained
in source even if an excessive/deep signature cannot be formatted.

Chunks preserve source exactly. Functions/methods stay whole when possible; large
ones split at line boundaries. Oversized lines split at Unicode character boundaries.
Line ranges are inclusive and one-based; character offsets are [start, end), using
Python Unicode characters, not JavaScript UTF-16 positions. The UI displays returned
chunk content directly. Parent metadata can be added to retrieval context later.

The current 8192-byte bound is deliberately not called a token limit. Token counting,
embedding generation, lexical/vector retrieval, merging, reranking and context
construction will be implemented and evaluated independently in Milestone 5 onward.
No LLM provider or embedding provider dependency is introduced in this milestone.

## Common errors

- No Source index panel: rebuild/restart frontend and open Browse files.
- relation repository_indexes does not exist: run the migration using the new image.
- Queued indefinitely: verify worker, dispatcher and Redis; inspect their safe logs.
- index_version_mismatch: rebuild/restart backend, worker and dispatcher together,
  then retry. Workers refuse jobs created for a different pipeline version.
- Syntax diagnostic: source may be invalid or target a newer Python grammar. The
  fallback is deliberate; compare original source rather than deleting the file.
- index_size_limit: choose a smaller repository; the cap is 10000 symbols/chunks.
- index_timeout/worker_lost: inspect resource usage and logs; use smaller source or
  configure the supported timeout range. Never disable resource bounds blindly.
- 409 after clicking twice: indexing is already active; observe its existing job.
- Source looks old: indexing uses the stored commit. Fetching newer commits remains
  postponed, and Check index does not fetch GitHub.

## Milestone status

Completed: static indexing, schema migration, durable jobs, authorized APIs, React
inspection, offline fixture inspection and test/upgrade instructions.
Verified: see docs/validation.md for tool-run results.
Next: local Docker/browser acceptance, then Milestone 5 hybrid retrieval/evaluation.
Postponed: model-specific tokenization, embeddings, retrieval, multi-language AST,
semantic route/model classification, successful-import refresh, incremental indexing,
retention cleanup, agents and execution sandboxes.

Suggested commit: feat(indexing): add versioned Python symbols and source chunks
