# Milestone 7A — Saved conversations and cited answers

## What we are building

Create a conversation for an imported repository, ask grounded questions inside it,
and reopen their answers and source references after a page reload. This is the
persistence slice of Milestone 7. Background runs, streaming/reconnection and model
conversation memory are still next; the overall milestone is not complete yet.

Why first: reliable streaming needs a durable home for completed messages. This
slice establishes ownership, transcript ordering, retention and a working React
history view before changing how answer jobs execute.

Flow: React conversation workspace → authorized conversation routes → conversation
service → existing retrieval/answer service → atomic message-pair transaction.
Old temporary questions still use POST /repositories/{id}/answers without storage.

Each question is independent. The UI says this explicitly; it does not pretend that
saved messages are already passed to the model. Ask self-contained questions until
we implement a bounded conversation-context policy in 7B.

## Exact files and implementation boundaries

New main files:

- backend/app/models/conversation.py — Conversation and Message ORM models.
- backend/migrations/versions/0006_conversations.py — additive Alembic migration.
- backend/app/repositories/conversation.py — ownership reads, pagination, pair append.
- backend/app/services/conversations.py — creation limits, authorization, generation/save.
- backend/app/schemas/conversation.py — validated titles and typed responses.
- backend/app/api/routes/conversations.py — thin session/CSRF-protected endpoints.
- frontend/src/features/conversations/api.ts — runtime-validated API client.
- frontend/src/features/conversations/ConversationWorkspace.tsx — create/select/delete.
- frontend/src/features/conversations/ConversationTranscript.tsx — paged saved messages.
- backend/tests/api/test_conversations.py — persistence and failure cases.
- backend/tests/integration/test_conversations_postgres.py — real concurrency check.
- frontend/tests/conversations.test.tsx — save/reopen/delete/history recovery.

Modified main files:

- backend/app/models/repository.py — supporting id/owner uniqueness constraint.
- backend/app/models/__init__.py and backend/app/main.py — model/router registration.
- frontend/src/features/answers/api.ts and AnswerPanel.tsx — optional saved-message route.
- frontend/src/features/repositories/FileBrowser.tsx — mounts conversation workspace.
- frontend/src/app/App.tsx and styles.css — milestone label and history layout.

The full exact path list is docs/milestone-7a-files.txt. Full final code and every
change are included in UPGRADE_FROM_MILESTONE_6.patch. ADR 0007 explains tradeoffs.
No new dependency, environment variable or infrastructure service is introduced.
Existing APP_ANSWERS_ENABLED/key/model settings retain their meaning; CRUD/history
reads require no model call. Real new answers still incur the existing provider cost.

## Database design and migration

Revision 0006_conversations follows 0005_hybrid_search.

Conversations store id, user_id, repository_id, title, message_count, created_at and
updated_at. A composite foreign key references repositories(id,user_id), preventing
an owner/repository mismatch even if application code has a bug. A new supporting
repository unique constraint makes that target valid. The repository/updated_at
index supports conversation listing.

Messages store id, conversation_id, turn_id, position, role, content, token_count,
answer JSON and created_at. The conversation foreign key cascades on deletion.
Unique (conversation_id,position) provides stable ordering and indexed page reads;
unique (turn_id,role) prevents duplicate roles within a completed question/answer
pair. Checks restrict roles, positive positions, nonnegative known token counts,
and assistant-only answer payloads. Tool is a permitted specification role, but
this slice never emits tool messages or executes tools.

The answer JSON is created only from validated server results. It retains exact
citations, source snippets, commit SHA, index/model/prompt metadata and accepted
usage estimates. We deliberately do not reference chunk rows with a foreign key:
reindexing must not destroy a historical answer's evidence. A copied snippet can
therefore outlive its index, but deleting the owning repository removes its history.

A short atomic counter update allocates adjacent positions before inserting both
rows in the same transaction. A failed insert rolls back the counter too. Ordering
is completion/publication order if requests overlap. No database lock spans the
external model call. user.token_count is unknown/null; assistant.token_count is
reported output usage, not a separate retokenization of displayed prose.

Existing users, repositories and indexes are preserved. Downgrading 0006 deletes
conversation/message history; it is not a routine troubleshooting step.

## Upgrade from Milestone 6

Extract the new archive separately, then copy UPGRADE_FROM_MILESTONE_6.patch into
your existing repopilot-ai root. Preserve .env, Git history and database volumes.
From that existing project root:

```bash
git apply --check UPGRADE_FROM_MILESTONE_6.patch
git apply UPGRADE_FROM_MILESTONE_6.patch
```

Both commands should complete without errors. If your local edits conflict, inspect
the exact affected files and merge them; do not force replacement over your work.
For a fresh checkout, use README.md's initial .env setup instead of applying a patch.

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
curl -i http://localhost:3000/api/health/live
```

Expected: revision 0006_conversations (head), no pending model/migration differences,
healthy PostgreSQL/Redis/backend, running frontend/worker/dispatcher and HTTP 200.
Migration SQL generation was checked here; actual PostgreSQL execution must be
validated locally. No .env changes are required if Milestone 6 already worked.

## Manual acceptance

1. Open http://localhost:3000, sign in and select Browse files on an imported repo.
   The header should read 07A / Saved conversations.
2. Under Conversations, enter a title and click Create conversation. It should be
   selected, show an empty transcript and remain available after a browser reload.
   This step works even if model generation is disabled.
3. With the existing source/search index ready and answers enabled, ask a specific
   question inside the selected conversation. Expect Answer saved and a cited answer.
4. Reload the page, reopen the repository and select that conversation. The exact
   question, answer, model usage, commit SHA and source links should reappear without
   another model request. Click a citation and compare its saved source text.
5. Ask a second self-contained question. Both complete pairs should appear. History
   displays the latest twenty messages, with Load older messages when needed.
6. Switch to Temporary question. Its result should not change the saved transcript.
7. Click Delete conversation, then Keep conversation: nothing should be deleted.
   Repeat and Confirm deletion: the conversation and its messages should disappear.
8. Use a second account. Direct reads/writes to the first account's conversation
   IDs must return 404. Automated tests cover all conversation endpoints.
9. Check keyboard controls, narrow layouts, long titles/code and history scrolling.

Validation gate: saved-answer reload, owner isolation, deletion and migration/drift
checks must work before moving to 7B. One successful answer is not a new model-quality
benchmark; the M6 evaluation dataset and provider behavior are unchanged.

## Run automated checks

From the project root:

```bash
cd backend
uv sync --frozen
uv run python -m app.embeddings.tokens
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

Expected: lint/types pass, 151 backend tests pass, and seven infrastructure tests
skip without opt-in. New API
tests use SQLite with foreign keys enabled and fake providers; they check saved
snapshots, authorization, failed-answer atomicity, cursor ordering, capacity,
composite owner enforcement, deletion cascades and deletion during generation.
They do not prove PostgreSQL concurrency. Actual measured counts are in validation.md.

From the project root in another terminal:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm check
pnpm test
pnpm build
```

Expected: checks pass, 28 component tests pass and dist/ is built. Tests include saved
answer reopening after remount without another generation call, working citations,
confirmation before deletion, history pagination/retry and session expiry.

## Real PostgreSQL/queue tests

Use a dedicated test database, never your application data. With Compose running,
from the project root create it once:

```bash
docker compose exec postgres sh -c 'createdb -U "$POSTGRES_USER" repopilot_test'
```

If it already exists, keep it. From the project root in Bash:

```bash
set -a
. ./.env
set +a
export APP_DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/repopilot_test"
export APP_REDIS_URL=redis://127.0.0.1:6379/1
export APP_ANSWERS_ENABLED=false
export APP_EMBEDDINGS_ENABLED=false
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run alembic current
uv run alembic check
RUN_DB_TESTS=1 RUN_QUEUE_TESTS=1 uv run pytest -m integration
```

Expected: 0006_conversations, no schema drift and seven infrastructure tests passing.
The new PostgreSQL test appends three turns concurrently in separate sessions and
checks unique adjacent positions, matching turn IDs and the final message count.
It uses synthetic validated answer objects and makes no model calls. Existing
PostgreSQL, pgvector, Redis and Celery checks remain included. These tests are
configured to run in CI, but were not executed in this tool environment.

## API contracts

Browser URLs have /api; direct FastAPI URLs omit that prefix. Each endpoint checks
session ownership; all writes use the existing Origin/custom-header/CSRF protection.

| Endpoint | Success | Behavior |
| --- | --- | --- |
| GET /api/repositories/{id}/conversations | 200 | Owned conversation list, newest updated first |
| POST /api/repositories/{id}/conversations | 201 | Body {"title":"Authentication"}; create empty conversation |
| GET /api/conversations/{id} | 200 | Owned metadata and saved message count |
| GET /api/conversations/{id}/messages | 200 | Latest 20 messages, ascending position, next_before cursor |
| GET /api/conversations/{id}/messages?before=21 | 200 | Up to 20 earlier messages |
| POST /api/conversations/{id}/messages | 201 | Generate, validate and atomically save a question/answer pair |
| DELETE /api/conversations/{id} | 204 | Delete conversation and its messages |

Example message body:

```json
{"question":"How does verify_token reject expired tokens?","mode":"keyword"}
```

The POST response is the existing typed AnswerResponse; GET messages returns role,
position, turn ID, content, nullable token_count and nullable full answer snapshot.
Clients cannot submit their own transcript roles or answer payloads. Title: trimmed,
nonblank, at most 100 characters, no control characters. Question/mode validation
is unchanged from M6. Limits: 100 conversations/repository, 20 creates/user/hour,
100 turns/conversation; existing per-user/deployment answer quotas still apply.

401 means expired/missing session; 403 is write protection; 404 includes foreign
resources; 409 means capacity or existing answer prerequisites; 422 invalid input;
429 shared request limit; 502/503 retain M6's safe provider/database error envelope.
Open http://localhost:8000/docs for complete schemas.

## Common errors and practical limits

- Header still 06: rebuild frontend and refresh the page.
- relation conversations does not exist: rebuild the migrate image and apply head.
- Blank conversation list after reload: reopen Browse files and select the saved
  conversation. Selected UI state is not persisted; the database history is.
- Answer disabled/search required: use the existing M6 configuration and M5 search
  preparation. Saving conversations does not enable paid generation automatically.
- Answer request timed out: click Refresh history before asking again. A completed
  answer may have committed even if its HTTP response was lost. Reads never charge.
- Provider/citation failure: no partial transcript is saved. This is deliberate.
- Conversation deleted while generating: publication returns 404 and does not
  recreate it; a model charge may already have occurred.
- Conversation full: create another one. A rare last-slot race can consume model
  cost before the publication limit rejects the later completion.
- History loading error: Retry history retries a read, not a model call.
- A follow-up like "what about that?" fails: history is stored but not model memory
  yet. Use a self-contained question until the next context-policy slice.

Stored questions, answers and quoted source are now user data. They are not logged
or exposed across users. Deleting a repository cascades to its transcripts. Normal
backup retention may outlive deletion; no erasure-from-backups guarantee is made.
Generation failures with unknown spend are still outside the saved-transcript usage
record. This is not durable financial accounting or exactly-once execution.

## Milestone status

Completed: 7A models/migration, saved-answer APIs, owner checks, React conversation
controls, history pagination, persistence/authorization tests and documentation.
Verified: see docs/validation.md. Local PostgreSQL/browser acceptance remains.
Next: 7B durable answer runs, idempotent submissions, bounded conversation context,
streaming/reconnect and durable usage accounting. Overall Milestone 7 remains open.
Postponed: local model adapter, held-out end-to-end RAG evaluation, advanced agents,
sandbox execution and public paid-deployment financial/abuse enforcement.

Suggested commit: feat(conversations): persist grounded questions and cited answers
