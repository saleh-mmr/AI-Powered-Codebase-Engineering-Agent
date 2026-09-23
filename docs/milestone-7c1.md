# Milestone 7C1 — bounded conversation context

7B was reported complete by the user. This archive implements the next independently
verifiable slice. It does not claim streaming: 7C2 will add streaming/SSE replay;
7C3 will complete per-call usage receipts and final MVP acceptance.

## What and why

Named background answers can now use recent dialogue to interpret follow-up
questions. For example, ask about verify_token, then ask what happens when it
expires. Earlier messages remain conversation context; new factual claims still
need citations to freshly retrieved code. Saved history alone was not model memory.

Architecture: React submission → owner-checked run service → frozen context snapshot
on the durable run → Celery worker → bounded retrieval/context construction →
validated structured answer → atomic saved transcript. Queue, cancellation, quotas,
source-index fencing, idempotency and paid-call retry rules remain from 7B.

## Implementation and exact paths

- backend/app/generation/history.py: typed HistoryTurn, deterministic limits and retrieval hint.
- backend/app/repositories/conversation_history.py: authorized recent complete-pair selection.
- backend/app/models/answer_run.py: history JSON snapshot.
- backend/migrations/versions/0008_answer_history.py: additive migration.
- backend/app/services/answer_runs.py: snapshot at submission inside the conversation lock.
- backend/app/jobs/answer_run.py: revalidate snapshot and pass it to generation.
- backend/app/jobs/answer_config.py: include history policy in configuration fingerprint.
- backend/app/generation/context.py and prompts/grounded_v2.txt: separate dialogue data from evidence.
- backend/app/services/answers.py: bounded retrieval hint and actual context provenance.
- backend/app/schemas/answer.py: backward-compatible provenance defaults for old snapshots.
- frontend/src/features/runs/RunComposer.tsx: updated follow-up and provider disclosure.
- frontend/src/features/answers/api.ts and GroundedAnswer.tsx: parse/display included history counts.
- backend/app/evaluation/answers.py and evaluation/answers/followups-v1/cases.json: reproducible fixture.
- backend/tests/unit/test_history.py and tests/api/test_answer_history.py: boundary/failure tests.

The archive contains full source, UPGRADE_FROM_MILESTONE_7B.patch and an exact changed
file list in docs/milestone-7c1-files.txt. No package dependencies were added.

## Engineering decisions

At most three consecutive recent answered turns from the same source index are
considered. An abstention, refusal, different index or malformed pair ends the
selection. Whole oldest pairs are omitted until history fits 1,000 estimated tokens
and 8 KiB. Current evidence has priority within the existing total 8,000-token /
64-KiB prompt bound. No model generates a hidden summary. Limits and policy live in
one module; change HISTORY_POLICY when intentionally changing selection semantics.

Snapshots contain turn IDs, questions and claim text, not old code snippets or
citation IDs. The worker uses the accepted snapshot even if new messages arrive.
Retries using the same request key do not resnapshot or create another run.
The latest retained user question supplements retrieval within its 512-character
bound. This is a simple hint, not model-based query rewriting; new-topic searches
can contain irrelevant prior terms. Explicit function/file names remain useful.

Saved AnswerResponse adds history_turn_ids, history_tokens and history_policy.
Old answers deserialize with empty/default values. history_tokens is an operational
estimate, not billing usage. Provider input_tokens remains the actual provider-reported
input count. No new request fields are accepted from the frontend. The old synchronous
POST /conversations/{id}/messages and temporary question endpoint keep empty history;
the React named-conversation workflow uses background runs and gets context.

Migration 0008 adds answer_runs.history JSON NOT NULL DEFAULT '[]'. Existing run
records keep empty snapshots. Existing unique indexes, owner joins and cascade FK
continue to apply; no new query index is needed for a small value read by run ID.
The existing (conversation_id, position) unique index supports newest-pair selection.
Downgrade removes snapshots; do not use it as routine troubleshooting. No schema
recreation or data reset is required.

## Upgrade and run

Wait for active runs to finish before upgrading. Previously queued 7B runs will
fail safely with answer_config_changed after this prompt/policy update; deliberately
resubmit only after checking their status. Never reset a running run to queued.

Extract this archive separately and copy UPGRADE_FROM_MILESTONE_7B.patch into your
existing project root. Keep .env, Git history and database volumes. From that root:

```bash
git apply --check UPGRADE_FROM_MILESTONE_7B.patch
git apply UPGRADE_FROM_MILESTONE_7B.patch
docker compose stop backend worker dispatcher frontend
docker compose build backend migrate worker dispatcher frontend
docker compose up -d postgres redis
docker compose run --rm migrate alembic upgrade head
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic check
docker compose up -d backend worker dispatcher frontend
docker compose ps -a
```

Success: head 0008_answer_history, no schema drift, infrastructure/backend healthy
and worker/dispatcher/frontend running. Inspect/merge local conflicts if patch check
fails; do not blindly replace existing files. For a fresh extraction, follow README
setup instead. Rebuild all application services to keep prompt fingerprints aligned.

No new environment variables. Existing APP_ANSWERS_ENABLED and APP_OPENAI_API_KEY
are needed for deliberate live answers. Existing price settings estimate costs.
The .env.example disclosure now includes selected past turns. Never place a key in
VITE variables. Local tests and fixture validation do not need a paid key.

## Manual validation

Open http://localhost:3000; header should read 07C1 / Conversation context.

1. Use an indexed repository with prepared keyword search and a named conversation.
2. Ask a specific symbol question and wait for a completed, grounded answer.
3. Ask a related follow-up. Confirm new source links work and the answer displays
   one prior turn (or a documented omission) with estimated history tokens.
4. Reload and reopen: the answer/provenance persists without another submission.
5. Open a separate conversation or Temporary question: prior context must be zero.
6. Inspect the included current evidence: the earlier answer must not be the sole
   support for a new claim. Check an explicit new-topic question for retrieval drift.

Live answers can incur charges. This implementation was tested with fake providers;
these steps are necessary to validate the local stack and actual model behavior.

## Automated validation

From repopilot-ai/backend:

```bash
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
uv run python -m app.evaluation.answers --check
uv run python -m app.evaluation.answers --check --dataset evaluation/answers/followups-v1/cases.json
```

Expected: lint/types/tests pass; seven infrastructure tests skip without opt-in.
Fixture checks report 8 and 4 cases, zero provider calls. First tokenizer use can
require a download; Docker images already cache the tokenizer. Tests cover bounded
whole-pair selection, evidence priority, malicious history as data, citation rejection,
frozen retry snapshots, cross-conversation/source isolation, abstention boundaries,
stateless compatibility and malformed snapshots failing before provider use.

From repopilot-ai/frontend:

```bash
pnpm install --frozen-lockfile
pnpm check
pnpm test
pnpm build
```

Expected: 32 component tests pass, checks pass and dist/ builds. New assertions
cover old-answer compatibility and visible included-history metadata.

Use the dedicated *_test PostgreSQL/Redis environment in docs/milestone-7a.md for
real infrastructure checks. From backend with those test variables configured:

```bash
uv run alembic upgrade head
uv run alembic check
RUN_DB_TESTS=1 RUN_QUEUE_TESTS=1 uv run pytest -m integration
```

Expected: all seven infrastructure tests pass. They are defined in CI but were
not run here. Never point test cleanup at your development data. See validation.md
for actual measured checks and evaluation.md for deliberate paid evaluation commands.

## Common errors and limitations

- history column missing: rebuild migrate and apply 0008 before starting the new backend/worker.
- answer_config_changed: align backend/worker builds and environment; old queued runs
  intentionally fail after prompt changes. Submit a new run only after reviewing status.
- zero prior turns: first question, source change, prior refusal/abstention, oversized
  latest pair, total prompt budget, temporary question or legacy synchronous route.
- poor pronoun resolution: name the function/file; no semantic rewrite or summary exists yet.
- stale UI: rebuild frontend and select a named conversation, not Temporary question.
- token count differs from provider: history estimate covers serialized dialogue only;
  provider usage covers the whole actual request with its billing tokenizer.

The application sends selected past questions/claims to the configured external model.
Snapshots persist with the run and cascade on deletion. Membership-validated citations
are not a proof of truth. No live answer-quality or full-stack pass is claimed here.

## Milestone status

Completed: frozen bounded context, prompt separation, retrieval hint, provenance UI,
additive migration, free checks and follow-up evaluation cases.
Verified: measured results in docs/validation.md; local Docker/browser acceptance pending.
Next: 7C2 streaming/SSE replay; overall Milestone 7 remains open.
Postponed: per-call usage receipts (7C3), semantic rewrite, summarization, long-term
memory, held-out end-to-end follow-up retrieval evaluation and agent execution.

Suggested commit: feat(chat): add bounded conversation context to background answers
