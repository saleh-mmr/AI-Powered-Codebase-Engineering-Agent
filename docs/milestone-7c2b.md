# Milestone 7C2B — real provider streaming and provisional answers

7C2A was reported complete by the user. This slice connects actual provider text deltas
to a clearly provisional draft in the named-conversation UI. Existing conversation
context, lifecycle replay, cancellation and final citation checks remain in place.
Fuller usage receipts and final MVP acceptance are next in 7C3.

## What we are building

While the worker receives model output, the user can read a draft marked “not yet
validated.” Only a complete validated result enters conversation history. A stream
failure must not convert partial text into a completed answer or start a second paid
request. Reopening an active run restores its latest draft without regenerating it.

Architecture: provider text deltas → bounded display projection → lease-fenced run
snapshot → owner-authorized SSE → React provisional text. In parallel, the adapter
accumulates the structured response; completed envelope/schema/citation validation
still controls atomic publication of the final answer and terminal event.

## Files and important implementation details

- backend/app/generation/contracts.py: optional StreamingAnswerProvider and typed DeltaSink.
- backend/app/generation/openai.py: shared request body and stream=true background transport.
- backend/app/generation/openai_stream.py: bounded SSE parsing, ordering/identity checks, final completion.
- backend/app/generation/openai_payload.py: shared final response validation for both transports.
- backend/app/generation/preview.py: partial JSON projection of claim/limitation text only.
- backend/app/jobs/answer_preview.py: throttled snapshot updates under the run lease.
- backend/app/services/answers.py and jobs/answer_run.py: controlled stream callback wiring.
- backend/app/models/answer_run.py and migrations/versions/0010_answer_preview.py: additive schema.
- backend/app/repositories/run_event.py: clear provisional text on terminal transitions atomically.
- backend/app/schemas/answer_preview.py, services/run_stream.py and api/routes/run_events.py: preview frames.
- frontend/src/features/runs/events.ts: separate snapshot revision from lifecycle cursor.
- frontend/src/features/runs/RunTimeline.tsx and RunComposer.tsx: provisional rendering/clearing.
- backend/app/evaluation/answers.py: streaming evaluation mode and first-delta measurement.
- backend/tests/unit/test_provider_stream.py, tests/api/test_answer_preview.py,
  frontend/tests/answer-preview.test.tsx: transport, fencing and rendering tests.

Full source, UPGRADE_FROM_MILESTONE_7C2A.patch and docs/milestone-7c2b-files.txt are in
the archive. ADR 0011 records the decision. No new dependency or environment variable.
The partial JSON parser already belongs to Pydantic. Its experimental partial mode is
used only for display; ordinary strict validation remains the final authority.

The adapter handles response.output_text.delta and response.completed. It ignores
reasoning/tool/refusal text for preview purposes and never exposes those raw events.
A completed response must match accumulated text and output identity. Invalid usage,
model mismatch, malformed envelopes, truncation, HTTP failure or out-of-order events
fail safely with no automatic retry. The provider protocol remains replaceable;
non-stream-capable adapters continue producing final-only answers.

The OpenAI contract was checked against official documentation on 2026-09-24:
- https://developers.openai.com/api/docs/guides/streaming-responses
- https://developers.openai.com/api/reference/resources/responses/streaming-events
- https://developers.openai.com/api/docs/guides/structured-outputs

## Bounds, security and cost

Drafts contain at most 8,000 Unicode characters and can be truncated independently
of the final answer. They are escaped plain text, with no HTML execution, links or
citation claims. Each snapshot replaces the previous one. Updates are at most once
per 250 ms and stop at 256 revisions. Browser observation uses the existing one-second
SSE poll, so multiple deltas can appear together. Fast responses may finish before a
draft is displayed. This is genuine provider streaming with coalesced UI updates.

Provider parsing caps total bytes at 2 MiB, a frame at 256 KiB, accumulated answer JSON
at 64 KiB and events at 12,000. Existing 60-second answer deadline and worker limits
remain. Browser SSE allows 64-KiB frames/2-MiB connections for bounded full snapshots.
No partial answer is appended to messages or used as conversation memory. All terminal
transitions clear preview text. Leases fence late writes after cancellation/expiry.
Expired-worker snapshots are hidden immediately on reads and cleared by dispatcher
expiry. Already displayed text cannot be recalled. Cancellation can stop local reading
on a subsequent write but does not guarantee avoiding provider charges.

The same configured model, prices, prompt and output limit are used. No extra model
call is introduced. Temporary questions and legacy synchronous endpoints stay final-only.
The shared final validator still handles refusals and no-evidence behavior. A new
transport fingerprint intentionally rejects queued runs from an older build.

## Database and API changes

Migration 0010_answer_preview follows 0009_run_events. It adds:

- preview_text TEXT NOT NULL DEFAULT '', checked to length <= 8000.
- preview_revision INTEGER NOT NULL DEFAULT 0, checked to 0..256.

Existing records default to an empty draft. No new index is needed: reads/writes use
the existing run primary key. Owner joins and cascade deletion remain. The fields are
excluded from ordinary RunResponse; only authorized opted-in SSE exposes a live draft.
Downgrade removes preview fields only, preserving runs/messages/events.

GET /answer-runs/{id}/events?preview=true adds:

```text
event: answer.preview
data: {"run_id":"00000000-0000-0000-0000-000000000001","revision":4,"text":"A growing draft"}

```

There is deliberately no id field. Last-Event-ID still refers only to lifecycle
sequence 1..3. Reconnect gets the current snapshot even if no new lifecycle event exists.
Terminal snapshots have empty text. Without preview=true the 7C2A contract is unchanged.
Session/header/owner checks and stream admission limits apply to both frame types.
The client ignores older snapshot revisions and never concatenates snapshots.

## Upgrade and run

Wait for active runs to finish. Old queued runs will fail with answer_config_changed
because the transport fingerprint changed; review status before deliberately resubmitting.
Do not reset running rows to queued. Extract separately and copy
UPGRADE_FROM_MILESTONE_7C2A.patch into your existing project root, preserving .env,
Git history and database volumes. From that root:

```bash
git apply --check UPGRADE_FROM_MILESTONE_7C2A.patch
git apply UPGRADE_FROM_MILESTONE_7C2A.patch
docker compose stop backend worker dispatcher frontend
docker compose build backend migrate worker dispatcher frontend
docker compose up -d postgres redis
docker compose run --rm migrate alembic upgrade head
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic check
docker compose up -d backend worker dispatcher frontend
docker compose ps -a
```

Success: 0010_answer_preview (head), no schema drift and running/healthy services.
Rebuild backend, worker and dispatcher together. Merge local patch conflicts instead
of overwriting unrelated work. Fresh installs follow README setup. No new .env values:
existing APP_ANSWERS_ENABLED/key/model/output/price settings still control paid answers.
Never put the provider key in frontend variables.

## Manual acceptance

Open http://localhost:3000; header should read 07C2B / Streaming answers.

1. Use a named conversation with prepared repository search. Submit a question that
   reasonably needs several factual explanations. Live answers can incur charges.
2. Watch “Draft — not yet validated.” It should grow as plain text with no source links.
   The final saved answer should replace it only after validation and show source links.
3. During a sufficiently long response, briefly disconnect/reconnect the browser or
   reload. The same run resumes from its current snapshot; no new submission appears.
4. Cancel during generation. The draft should disappear once the terminal update or
   fallback poll arrives; no late answer should be saved. Charges may already exist.
5. Reopen a completed/failed/cancelled run: no provisional text should replay. The
   validated answer, if any, remains in history. Temporary questions stay final-only.
6. Check session expiry/access behavior from 7C2A with preview enabled.

Fast responses may complete within the one-second observation interval; use the mock
UI tests below to verify intermediate states deterministically instead of raising
output limits or repeatedly spending money just to see animation.

## Automated validation

From repopilot-ai/backend:

```bash
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
uv run python -m app.evaluation.answers --check --stream
uv run python -m app.evaluation.answers --check --stream --dataset evaluation/answers/followups-v1/cases.json
```

Expected: checks/tests pass; seven infrastructure tests skip without opt-in. Fixture
checks report 8 and 4 valid cases and zero provider calls. New tests cover fragmented
provider SSE, strict stream request flags, event identity/order, completion mismatch,
usage errors, truncated/oversized streams, refusal/reasoning suppression, partial
projection, callback fencing/throttling, terminal clearing and snapshot reconnect.
They mock paid providers. Normal generation tests still exercise the buffered adapter.

From repopilot-ai/frontend:

```bash
pnpm install --frozen-lockfile
pnpm check
pnpm test
pnpm build
```

Expected: 48 tests pass, checks pass and dist/ builds. New tests check snapshot
replacement, revision ordering, payload limits, escaped HTML, absent source links,
terminal clearing and stale-draft hiding when polling observes failure.

For real PostgreSQL/Redis/Celery use the dedicated *_test procedure in milestone-7a.md.
From backend, with those isolated variables already configured:

```bash
uv run alembic upgrade head
uv run alembic check
RUN_DB_TESTS=1 RUN_QUEUE_TESTS=1 uv run pytest -m integration
```

Expected: seven infrastructure tests pass. They do not replace the live-provider and
browser streaming checks above. Do not run test cleanup against development data.
See validation.md for actual measured results and outstanding gates.

## Evaluation and common errors

The evaluation runner accepts --stream with --allow-paid. See evaluation.md for exact
buffered-versus-streamed commands on the existing fixtures. It records first_delta_ms
and transport alongside final metrics; first delta may contain JSON syntax and is not
browser-visible draft latency. No paid evaluation or latency claim is made here.

- Missing preview columns: rebuild migrate and apply 0010 before starting new services.
- answer_config_changed: align builds; old queued runs intentionally require a new submission.
- No draft: use a named background conversation; a fast response, no evidence, refusal,
  non-stream-capable replacement adapter or omitted preview=true can all yield final-only output.
- model_incomplete: the stream ended/failed before a successful completed response; partial
  text was not saved. Check run status/usage before deliberately trying again.
- model_invalid: envelope/order/identity/output checks failed. Never bypass validation.
- Draft vanishes: expected on terminal state, stream interruption or expired lease. Reconnect
  restores it only if the same run still has a live snapshot.
- Draft stops growing at its display bound: the final output still has its separate model cap.
- Events batch together: inspect proxy buffering; the included Nginx already disables it.
- Unknown usage after failure/cancel: unchanged limitation, addressed by 7C3 receipts.

## Milestone status

Completed: provider text streaming, bounded provisional snapshots, fenced writes,
SSE recovery, React draft states, migration, transport evaluation and tests.
Verified: measured results in validation.md; local Docker/browser/live-provider acceptance pending.
Next: 7C3 per-call usage receipts and final repository-understanding MVP acceptance.
Postponed: full billing reconciliation, deployment load tests, sub-second shared fanout,
advanced agents and autonomous code execution.

Suggested commit: feat(streaming): add provisional provider output with safe finalization
