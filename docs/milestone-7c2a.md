# Milestone 7C2A — durable live run timeline

7C1 was reported complete by the user. This slice adds real lifecycle event streaming,
reconnect and replay. It is the first part of 7C2. The specification's token-by-token
answer streaming remains 7C2B, followed by fuller usage receipts in 7C3. The current
provider adapter and prompts are unchanged; no fake typing animation is used.

## What we are building and why

The newest run in a named conversation now has a live timeline: queued → running →
completed, failed or cancelled. Reloading replays stored events; a transient disconnect
resumes after the last received sequence. Generation is independent of its observers.
The completed answer still appears only after structured-output/citation validation.

Architecture: submit/worker/cancel/expiry transaction → PostgreSQL lifecycle event →
authorized SSE reader → React timeline → refresh current run and completed history.
Read-only streaming does not generate, retry or cancel model requests. Status polling
continues every 10 seconds as a fallback instead of the previous active 2-second poll.

## Files and implementation

- backend/app/models/run_event.py and schemas/run_event.py: compact typed lifecycle event.
- backend/migrations/versions/0009_run_events.py: table, constraints, baseline backfill.
- backend/app/repositories/run_event.py: sequence allocation under an existing run write lock.
- backend/app/services/answer_runs.py: submission and cancellation events.
- backend/app/jobs/answer_run.py: claimed, completed and failed events.
- backend/app/jobs/answer_dispatcher.py: expired queue/worker events.
- backend/app/services/run_stream.py: bounded replay/polling, repeated auth, heartbeat and safe errors.
- backend/app/api/routes/run_events.py and main.py: authenticated stream route/registration.
- frontend/src/features/runs/events.ts: bounded incremental SSE decoder and HTTP error handling.
- frontend/src/features/runs/RunTimeline.tsx: connection state, cursor, backoff and unmount cleanup.
- frontend/src/features/runs/RunComposer.tsx: newest-run timeline and fallback polling.
- backend/tests/api/test_run_events.py, tests/unit/test_event_migration.py,
  frontend/tests/run-events.test.tsx: transport, access, replay and atomicity tests.

Full source, UPGRADE_FROM_MILESTONE_7C1.patch and exact paths in
 docs/milestone-7c2a-files.txt are included. ADR 0010 explains the design. No dependency,
provider, prompt or environment variable changes. .env.example remains accurate.

## Database change

0009_run_events follows 0008_answer_history. answer_run_events stores run_id (cascading
FK), sequence, status and occurred_at. The composite primary key (run_id, sequence)
uniquely orders replay and indexes per-run reads. Checks allow only existing lifecycle
statuses and sequence 1..3. No question/source text is duplicated into event rows.

An accepted run inserts queued in the same transaction. A successful claim inserts
running. Only a successful terminal transition appends its event. Completion also
saves both messages and usage atomically. Cancellation, worker failure and dispatcher
expiry use the same rule. Rollback cannot leave a phantom completed event. Rows live
until their parent run/conversation is deleted. Current retention is at most three
small rows per run, within the existing run/conversation quotas.

Existing runs receive one baseline entry with their current state and available
transition timestamp. Historical transitions are not reconstructed. Run/message/history
data is preserved. Downgrading removes event history only; avoid it for routine fixes.
Backfill runs in the migration transaction, so plan a maintenance window for large data.

## API contract

GET /answer-runs/{run_id}/events requires the session cookie and X-RepoPilot-Request: 1.
Use Accept: text/event-stream. Last-Event-ID (0..3) takes precedence over ?after=0..3.
0 means replay all available entries. A future cursor returns 409; malformed input
returns 422. Authentication/ownership/header failures return 401/404/403 before the
stream opens. Admission limits can return 429, with Retry-After: 60.

Example event (line breaks and blank final line matter):

```text
id: 2
event: run.status
data: {"run_id":"00000000-0000-0000-0000-000000000001","sequence":2,"status":"running","occurred_at":"2026-09-23T12:00:00Z"}

```

Control events have no ID: stream.end closes terminal replay; stream.reconnect asks
the client to reopen after approximately 25 seconds; stream.error closes after a
safe authentication/access/service error. Comment heartbeats occur every five polls.
The client never advances its cursor for controls or heartbeats. A truncated EOF is
an interruption, not completion. The same run ID with a newer cursor only reads data.
No secret belongs in the URL. Auth/ownership are rechecked each poll; there is no
long-lived database transaction. Nginx already has proxy_buffering off and a 70-second
read timeout; Vite proxies the same endpoint in host development.

## Upgrade and run

Let active runs finish before stopping services. Extract separately and copy
UPGRADE_FROM_MILESTONE_7C1.patch into your existing repopilot-ai project root. Preserve
.env, Git history and database volumes. From that root:

```bash
git apply --check UPGRADE_FROM_MILESTONE_7C1.patch
git apply UPGRADE_FROM_MILESTONE_7C1.patch
docker compose stop backend worker dispatcher frontend
docker compose build backend migrate worker dispatcher frontend
docker compose up -d postgres redis
docker compose run --rm migrate alembic upgrade head
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic check
docker compose up -d backend worker dispatcher frontend
docker compose ps -a
```

Expected: 0009_run_events (head), no schema drift, healthy infrastructure/backend and
running worker/dispatcher/frontend. Rebuild all services: older workers do not append
events. Unlike the prior prompt update, this slice does not change run configuration
fingerprints. Fresh installs follow README .env setup. If a patch conflicts with local
changes, merge the listed final files rather than overwriting unrelated work.

## Manual validation

Open http://localhost:3000; the header should read 07C2A / Live run timeline.

1. Open a named conversation and submit a question. Its newest-run timeline should
   show queued, running and a terminal state. Completed answers retain source links.
2. Reload/reopen that conversation. Stored transitions replay without a new submission.
   An older pre-upgrade run correctly shows only its current-state baseline.
3. For a free queued-state check, stop an idle worker with docker compose stop worker,
   submit a run, and use browser Network → Offline briefly. Restore online; the timeline
   reconnects while the same run ID remains. Start it with docker compose start worker
   only if you intend generation charges; otherwise cancel the queued run first.
4. Inspect the GET events request: text/event-stream, no-store and incremental frames.
   Reconnect requests carry Last-Event-ID. No new POST submission should appear.
5. Open the same account in a second tab; log out there. The first stream should close
   on its next access check. Existing polling/session handling returns to authentication.
6. Cancel queued work: timeline should end at cancelled; no answer should be published.

Disconnecting the page never stops paid generation. Cancellation retains the existing
publication fence but cannot guarantee stopping or refunding a provider call. No model
calls are needed for terminal replay, tests, or inspection of an existing run.

## Automated validation

From repopilot-ai/backend:

```bash
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

Expected: lint/types/tests pass; seven infrastructure tests skip unless explicitly
configured. New tests cover sequence replay/cursor precedence, duplicate worker
execution, cancellation/failure, header/owner/session boundaries, invalid cursors,
heartbeat/reconnect, logout/deletion/disconnect, rate limits and event-write rollback.
The portable migration test checks one baseline per old run and data-preserving
downgrade; it is not proof of PostgreSQL locking behavior.

From repopilot-ai/frontend:

```bash
pnpm install --frozen-lockfile
pnpm check
pnpm test
pnpm build
```

Expected: 41 tests pass, checks pass and dist/ builds. New tests cover fragmented CRLF
frames, duplicate IDs, schema/identity/sequence failures, oversized frames, truncated
streams, session expiry, reconnect cursors, read-only requests and abort on unmount.

For real PostgreSQL/Redis/Celery use the dedicated *_test environment documented in
milestone-7a.md. From backend with those test variables configured:

```bash
uv run alembic upgrade head
uv run alembic check
RUN_DB_TESTS=1 RUN_QUEUE_TESTS=1 uv run pytest -m integration
```

Expected: seven infrastructure checks pass. Do not point test cleanup at development
data. These checks and proxy/browser acceptance were not run in this environment;
see validation.md for measured results. Provider behavior and evaluation fixtures are
unchanged, so no new paid quality evaluation is required for this transport-only slice.

## Common errors and limits

- relation answer_run_events missing: rebuild migrate and apply 0009 before new services.
- Timeline missing: use the newest run in a named conversation and rebuild frontend.
- Only one entry on an older run: expected migration baseline; prior events were not saved.
- Stream returns 403: required X-RepoPilot-Request header is missing. Native EventSource
  cannot set it; the shipped client uses fetch. Do not put credentials in URLs.
- 409 cursor ahead: refresh/reopen the conversation to reset its cursor and replay.
- 429: too many connections/tabs; the client waits 60 seconds and ordinary polling continues.
- Events arrive together: check reverse-proxy buffering. The included Nginx config disables it.
- Run stays queued: investigate dispatcher/worker; reconnecting the reader will not start work.
- Unknown usage after failure: unchanged from 7B; live updates are not provider receipts.

Connection starts are capped at 30/minute and 300/hour per user, not a global concurrent
connection limit. The current implementation polls PostgreSQL once per second per open
stream with bounded metadata reads and closes its connection between polls. Measure
active-viewer load before introducing shared notifications. Stream duration is logged
as run_stream_closed; request_completed measures time to response headers. No question,
source content, cookies or model output is logged by the streaming layer.

## Milestone status

Completed: atomic lifecycle events, migration/backfill, owner-scoped SSE, reconnect
and replay, React timeline, rate bounds and tests.
Verified: measured local results in validation.md; full-stack local acceptance pending.
Next: 7C2B real provider token streaming and a clearly provisional answer interface.
Postponed: fuller per-call usage receipts (7C3), deployment load testing, stage/tool
telemetry and agent actions. Overall Milestone 7 is still in progress.

Suggested commit: feat(streaming): add durable run timeline with SSE replay
