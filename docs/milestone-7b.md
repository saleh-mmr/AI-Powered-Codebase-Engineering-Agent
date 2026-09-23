# Milestone 7B — Durable background answers

This archive contains the actual 7B implementation, including the full application
and UPGRADE_FROM_MILESTONE_7A.patch. The prior 7A download does not contain this feature.

## What we are building and why

Submit a question, receive a durable run ID, then close or reload the browser while
an existing Celery worker retrieves evidence and generates the answer. Reopen the
conversation to see the run state and saved result. Cancellation and failure are
visible instead of leaving an indefinitely spinning HTTP request.

The engineering distinction: an idempotent submission creates one run, while a worker
claim prevents duplicate broker messages from starting that run again. Neither is
an exactly-once billing guarantee for an external provider. We fail uncertain running
attempts instead of automatically repeating a potentially paid call.

7B covers execution reliability, polling/reload recovery and stored completed usage.
7C will add streaming/replay and bounded conversation memory. Questions still need
to be self-contained. The overall streaming MVP milestone remains open.

## Architecture and implementation files

React Queue answer → authenticated run API → committed PostgreSQL AnswerRun → existing
dispatcher → existing Celery worker → retrieval/validated generation → atomic run
completion + question/answer messages. React reads status and refreshes history.

New files:

- backend/app/models/answer_run.py — durable state, uniqueness and usage constraints.
- backend/migrations/versions/0007_answer_runs.py — additive schema migration.
- backend/app/schemas/answer_run.py — typed submission/status/list contracts.
- backend/app/repositories/answer_run.py — owner-scoped reads and key lookup.
- backend/app/services/answer_runs.py — idempotency, admission, cancellation.
- backend/app/api/routes/answer_runs.py — thin authenticated endpoints.
- backend/app/jobs/answer_config.py — safe configuration fingerprint.
- backend/app/jobs/answer_run.py — atomic claim and fenced transcript publication.
- backend/app/jobs/answer_dispatcher.py — queued delivery and conservative expiry.
- frontend/src/features/runs/api.ts and RunComposer.tsx — queue/status/cancel/recovery UI.
- backend/tests/api/test_answer_runs.py and frontend/tests/runs.test.tsx.

Modified files include backend/app/jobs/celery_app.py, jobs/dispatcher.py,
services/answers.py (internal source-index guard), main.py, models/__init__.py,
frontend/src/features/conversations/ConversationWorkspace.tsx, App.tsx, styles.css,
and existing conversation/worker integration tests. Full exact paths are listed in
docs/milestone-7b-files.txt. Full code and the exact patch are included in this archive.

No provider API, prompt, package dependency or environment variable changes. Existing
M6/M7A synchronous endpoints keep their contracts for compatibility. Named conversations
in the updated React UI use the new run endpoints; Temporary question stays synchronous.

## Database migration and constraints

0007_answer_runs follows 0006_conversations. It creates answer_runs with a cascading
conversation foreign key, request key/hash, question/mode, source-index ID, config
hash/model, status, usage fields, error fields, dispatch timestamp and lease metadata.

- Unique (conversation_id,request_key) prevents duplicate accepted submissions.
- Partial unique conversation_id where status is queued/running permits one active
  background run per conversation. Terminal runs release the slot.
- The status/created_at index supports dispatcher scans.
- Checks restrict status/mode/usage state and nonnegative known tokens/cost.
- Source-index ID is provenance rather than a foreign key: removing an index must
  not erase the run record. The worker rejects a changed source before generation.

Run completion and both transcript messages commit together. Concurrent deletion
or cancellation prevents late publication. Existing users, repositories, indexes and
saved messages are preserved. Downgrading 0007 deletes run records, not previously
saved transcript pairs. Do not downgrade as routine troubleshooting.

Known completed usage is stored; unknown costs are null, never silently reported as
zero. The run's input/output counts refer to generation; its total estimate also
includes successful query embedding cost. Full source/model metadata remains in the
saved answer snapshot. Failed attempts can incur charges without recorded totals.

## Upgrade from 7A and run

Extract this archive separately. Copy UPGRADE_FROM_MILESTONE_7A.patch into your existing
repopilot-ai root, preserving .env, Git history and database volumes. From that root:

```bash
git apply --check UPGRADE_FROM_MILESTONE_7A.patch
git apply UPGRADE_FROM_MILESTONE_7A.patch
docker compose stop backend worker dispatcher frontend
docker compose build backend migrate worker dispatcher frontend
docker compose up -d postgres redis
docker compose run --rm migrate alembic upgrade head
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic check
docker compose up -d backend worker dispatcher frontend
docker compose ps -a
```

Expected: patch applies cleanly, migration head is 0007_answer_runs, no schema drift,
and backend/PostgreSQL/Redis are healthy with worker/dispatcher/frontend running.
If local edits conflict, inspect and merge the affected final files; do not overwrite
your repository blindly. For a fresh checkout, use README.md's .env setup first.

**Rebuild and restart the worker and dispatcher as well as the backend.** An old
worker will not recognize the new task; an old dispatcher will not discover runs.
Existing answer settings must be consistent in backend and worker. If you changed
APP_ANSWERS_ENABLED/key/model only on the backend during M6, recreate the worker now.
The Compose environment already passes these settings to both. Never use VITE keys.

Open http://localhost:3000. The header should read 07B / Background answers.
Choose Browse files → an existing named conversation → Ask in the background.
The button is Queue answer. It is not shown in Temporary question mode.

## Manual acceptance

1. Keep a completed source index and prepared keyword search from prior milestones.
   Enable answers using the existing M6 configuration only if you intend real charges.
2. Select a named conversation and submit a self-contained question. It should quickly
   show queued, then running, then completed. It should not hold a generation HTTP request.
3. Close the repository view or reload. Reopen the same conversation. Its run should
   remain visible, and its completed answer/citations should appear in saved history.
4. Inspect browser Network: POST /api/conversations/{id}/runs returns 202 with an ID;
   subsequent GET requests only read status. A same-key replay returns 200 and the same ID.
5. Verify the saved answer's citation targets, source snapshot and known usage estimate.
6. To test safe queued cancellation, stop only the worker from the project root:

```bash
docker compose stop worker
```

Queue another question, then click Cancel answer. Expect cancelled and no saved pair.
Restart the worker from the project root:

```bash
docker compose start worker
```

The cancelled run must not execute even if its old broker message is delivered.
Do not stop a live paid worker just to test crash recovery; mocked tests cover that
path without charges. Cancellation after a call starts cannot promise no charge.
7. Use a second account to check that the original run's GET/cancel and conversation
   run-list/submission endpoints return 404. Automated tests cover these boundaries.
8. Check keyboard controls, narrow layout, disabled duplicate submission, failure
   messages and Refresh run status. History loading failures should not resubmit.

Validation gate before 7C: migration/drift checks, queued cancellation, successful
background completion and reload recovery must pass in your local stack.

## API contracts

Browser URLs include /api; direct FastAPI URLs omit it. Session ownership is checked
on every operation. POST routes require the existing Origin/custom-header/CSRF proof.

| Endpoint | Success | Contract |
| --- | --- | --- |
| POST /api/conversations/{id}/runs | 202 new / 200 replay | question, mode and request_key UUID |
| GET /api/conversations/{id}/runs | 200 | Up to 20 recent runs, newest first |
| GET /api/answer-runs/{id} | 200 | Durable state, safe error and usage metadata |
| POST /api/answer-runs/{id}/cancel | 200 | Body {}; cancel queued/running publication |

Example submission:

```json
{"question":"How does verify_token reject expired tokens?","mode":"keyword","request_key":"f68c26a2-cfc0-42bf-91dc-44b53424bfcb"}
```

Generate a new UUID for a genuinely new submission. Retry an uncertain submission
with its same UUID, question and mode. Do not reuse one key for different questions.
A failed/cancelled/completed run replay does not restart work; a deliberate new attempt
requires a new key. No automatic regeneration is performed.

Responses include id, conversation_id, request_key, question, mode, model, source
index, status, usage_state, nullable input/output/cost, safe errors and timestamps.
Full schemas are available at http://localhost:8000/docs. Raw provider bodies, keys,
connection URLs and hidden reasoning are not returned.

401: authentication. 403: CSRF. 404: missing/foreign resource. 409: active/full run,
idempotency conflict or missing generation/search prerequisites. 422: invalid inputs.
429: admission quota. 503: unavailable request protection/database. Worker failures
are durable failed statuses rather than changing a previously accepted HTTP response.

Admission limits: 10 new submissions/minute/user, 60/day/user, at most 1000 retained
runs/conversation and one active background run per conversation. Existing model-call
quotas remain enforced when the worker executes (5/minute, 30/day/user and the configured
deployment cap). These controls are not a financial ledger or public anti-abuse policy.

## Recovery and cost semantics

Queued broker publication may repeat after thirty seconds; atomic claiming makes
those deliveries harmless. Running work is not reclaimed. Lease expiry after 180
seconds becomes answer_worker_lost, with no automatic retry. A run queued for more
than one hour becomes answer_queue_expired. The dispatcher must be alive for expiry.

usage_state not_started means no worker attempt. unknown means an attempt began but
its result/usage did not commit, including some failures before a provider call. It
is conservative and does not assert a charge occurred. recorded means completed
usage and the transcript committed together. Do not sum unknown usage as zero.

Source/configuration change causes a visible failure; a new explicit submission
uses the new setup. Hybrid query embedding can cost money before source-change
rejection. No source is executed, and the model has no additional tools.

Closing the browser only stops polling; it does not cancel the run. A successful
cancel prevents future transcript publication but may not stop an already accepted
provider call. Deletion cascades to run records and blocks publication. Full per-call
usage receipts, provider reconciliation and streaming event replay remain postponed.

## Automated tests: no paid calls

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

Expected: lint/types/tests pass; seven infrastructure tests skip without opt-in.
New tests cover same-key replay/conflict, single active run, duplicate worker delivery,
atomic completion, known usage, queued/running cancellation, failure without retries,
queued expiry, worker-loss recovery, source/configuration changes and owner/CSRF checks.
Tests use fake providers. SQLite tests do not prove PostgreSQL locking behavior.
See docs/validation.md for exact measured results and outstanding infrastructure gates.

From the project root in another terminal:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm check
pnpm test
pnpm build
```

Expected: checks pass, 31 component tests pass and dist/ is built. Tests exercise
reload recovery, safe same-key resubmission, cancellation, unknown usage, completion
history refresh and the existing source/answer workflows.

For real PostgreSQL/Redis/Celery, use the isolated repopilot_test procedure in
milestone-7a.md, applying the new head 0007_answer_runs before tests. From backend/
with its dedicated *_test database and Redis test environment already configured:

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic check
RUN_DB_TESTS=1 RUN_QUEUE_TESTS=1 uv run pytest -m integration
```

Expected: all seven infrastructure tests pass. The existing real Celery roundtrip
now includes answer generation with a fake provider, native PostgreSQL retrieval,
duplicate task delivery and saved run/message/usage checks. It makes no paid call.
It is included in CI but has not been executed in this tool environment.

## Common errors

- Cannot see 7B: use this archive, rebuild frontend, select a named conversation;
  Temporary question intentionally keeps the old immediate-answer interface.
- relation answer_runs does not exist: rebuild migrate and apply 0007.
- queued indefinitely: check docker compose logs dispatcher worker; both must use
  the new image and the same PostgreSQL/Redis configuration.
- unregistered task repopilot.answer_run: restart the rebuilt worker.
- answers_disabled inside a run: worker has stale/disabled settings; recreate it.
- answer_config_changed: backend/worker disagree about model, output cap, prices or
  prompt/retrieval version. Align their builds/configuration, then submit a new run.
- answer_source_changed: indexing changed after acceptance. Submit a new run deliberately.
- answer_worker_lost: no automatic paid retry was attempted; inspect before retrying.
- unknown usage: null is intentional, not a free-call claim. Check provider accounting.
- idempotency_conflict: the key belongs to a different payload. Recover the original
  run or use a new key for a genuinely new question.
- 409 on cancel: the run may have completed first. Refresh status and history.

## Milestone status

Completed: durable run API/schema, idempotent submission, worker/dispatcher execution,
cancellation, conservative worker-loss handling, React polling/reload recovery and tests.
Verified: see docs/validation.md. Local Docker/PostgreSQL/queue/browser acceptance remains.
Next: 7C streaming/replay and bounded conversation memory; overall Milestone 7 stays open.
Postponed: full financial reconciliation, per-call usage receipts, history-aware
retrieval evaluation, local providers and advanced agent execution.

Suggested commit: feat(runs): add durable background answers and idempotent submission
