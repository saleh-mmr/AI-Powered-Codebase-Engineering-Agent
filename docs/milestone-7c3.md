# Milestone 7C3 — finish the repository-understanding MVP

7C2B was reported complete by the user. This delivers the remaining Milestone 7 code;
Milestone 8 is not started. Local stack/browser acceptance remains a separate gate.

## What changed and why

Known provider usage now survives rejected answers and cancellation. The worker injects
a ReceiptWriter into generation and retrieval services. It commits an attempt before a
provider call, then stores usage separately from transcript publication. The model
adapter carries valid usage through safe output-validation errors. This demonstrates
why a transaction boundary should follow a business invariant: saving a valid answer
and observing a paid call are different facts.

- backend/app/models/usage_receipt.py and migrations/versions/0011_usage_receipts.py:
  additive receipt table plus answer_runs.receipt_version. The run FK cascades deletion;
  unique (run_id, kind) is also the run lookup index. Constraints reject negative rates
  and partially populated usage. Nullable counts mean unknown, never zero.
- backend/app/services/usage_receipts.py: independent attempt/completion transactions,
  active lease check before dispatch, immutable first completion and no resurrection.
- backend/app/services/answers.py, services/search.py and jobs/answer_run.py: explicit
  receipt wiring around generation and query embedding. Citation validation stays strict.
- backend/app/core/provider_usage.py, generation/openai_payload.py,
  generation/openai_stream.py and embeddings/openai.py: preserve independently validated
  usage when output is rejected. Truncation without trustworthy usage remains unknown.
- backend/app/schemas/usage_receipt.py, services/answer_runs.py and api/routes/answer_runs.py:
  typed owner-protected GET /answer-runs/{id}/usage (browser proxy adds /api).
- frontend/src/features/runs/RunUsage.tsx, RunComposer.tsx and api.ts: per-run expandable
  receipts with loading/error/retry/legacy states and a known subtotal.
- Tests cover failed/cancelled calls, duplicate delivery, recorded-before-call ordering,
  authorization, immutable completion, deletion, invalid usage, and UI unknown/legacy states.
  The existing PostgreSQL conversation integration test now verifies receipt persistence
  after cancellation and cascading deletion on the real database.

See milestone-7c3-files.txt for every changed path and the included exact upgrade patch.
No new dependencies or environment variables. Existing APP_ANSWER_INPUT_PRICE_PER_MILLION,
APP_ANSWER_OUTPUT_PRICE_PER_MILLION and APP_EMBEDDING_PRICE_PER_MILLION set estimates.
Keep .env private; verify configured rates yourself before interpreting costs.

## Upgrade from 7C2B

Commit or back up local changes first. Extract this archive to a separate directory.
Copy UPGRADE_FROM_MILESTONE_7C2B.patch from the extracted project into your existing
repopilot-ai root. In that existing root:

```bash
cd repopilot-ai
git apply --check UPGRADE_FROM_MILESTONE_7C2B.patch
git apply UPGRADE_FROM_MILESTONE_7C2B.patch
```

Success: both commands exit 0. If the check reports a conflict, stop and inspect the
reported file; do not force the patch over local changes. The archive includes complete
final source for comparison. The patch does not replace .env, Git history or DB volumes.

From the same root, stop old application processes, migrate, then start matching builds:

```bash
docker compose stop frontend backend worker dispatcher
docker compose build
docker compose run --rm migrate alembic upgrade head
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic check
docker compose up -d
docker compose ps -a
```

Expected: 0011_usage_receipts (head), no new schema operations, migration exit 0, backend
and dependencies healthy, frontend/worker/dispatcher running. Never use down -v for an
upgrade. In-flight runs should finish before upgrading if their result matters. Old
queued configuration hashes intentionally fail with answer_config_changed: resubmit
explicitly after checking status. Old receipts are not backfilled with invented usage.

For a fresh clone/extraction use README.md startup and .env setup. Open localhost:3000,
open a named conversation, queue an answer and expand Call usage receipts. After it
finishes, Refresh receipts should show generation counts and, in hybrid mode, a separate
query embedding receipt. UI estimates are not provider invoices.

## Checks (no paid calls)

From repopilot-ai/backend:

```bash
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest -q
uv run python -m app.evaluation.answers --check --stream
uv run python -m app.evaluation.answers --check --stream --dataset evaluation/answers/followups-v1/cases.json
```

Expected: checks pass, portable tests pass, seven infrastructure tests skip unless opted
in; fixture validation reports 8 and 4 cases, zero provider calls. Actual measured counts
are in validation.md. For infrastructure use the isolated *_test database procedure in
milestone-7a.md with the new head, then RUN_DB_TESTS=1 RUN_QUEUE_TESTS=1 uv run pytest -m
integration. Those seven tests must pass before accepting the local stack.

From repopilot-ai/frontend:

```bash
pnpm install --frozen-lockfile
pnpm check
pnpm test
pnpm build
```

Expected: checks pass, 51 tests pass, dist/ builds. Complete mvp-acceptance.md before
starting Milestone 8. Paid model evaluation remains explicitly opt-in; ordinary tests
use controlled providers. No paid evaluation or production latency claim was made here.

## API behavior and limits

GET /answer-runs/{id}/usage requires the session cookie and ownership of both conversation
and repository. Another user's ID returns 404; unauthenticated requests return 401.
Response: tracked:boolean, items:ReceiptResponse[], known_cost_usd:decimal-string,
unknown_calls:integer. Each item has id, kind, model/profile, decimal-string input_rate
and output_rate, nullable token counts/cost, started_at and nullable finished_at.
A tracked empty list means no attempt has been recorded yet, not that a running job
cannot later incur cost. Legacy tracked=false means coverage is unavailable.

There are at most two receipts per run under the current workflow. The known subtotal
excludes unknown calls, indexing and standalone requests. Rates are frozen; adjustments,
cached-input discounts and actual invoice reconciliation are postponed. No automatic
paid retry is introduced. Cancellation can race with an already-starting provider call;
receipt completion may arrive after cancellation, so the UI has an explicit refresh.

## Common errors

- Missing usage_receipts or receipt_version: apply 0011 before starting the new builds.
- answer_config_changed: align API/worker versions and submit a new run deliberately.
- Unknown call: provider/transport/worker/DB failed before trustworthy usage was saved.
  Inspect status and provider billing before retrying; do not convert missing usage to zero.
- Known receipt but failed answer: expected for rejected citations/schema or cancellation.
- Usage endpoint 404: wrong/deleted run or ownership mismatch; do not loosen authorization.
- Receipt list disappears after deleting its conversation: expected cascading deletion.
- Migration drift: ensure ORM and migration files came from the same release.

Suggested commit: feat(usage): persist call receipts and finish milestone 7 MVP

Milestone status:
Completed: remaining Milestone 7 implementation, migration, receipt UI, tests, acceptance procedure.
Verified: available automated checks in validation.md.
Next: run local infrastructure/browser acceptance; then discuss Milestone 8 separately.
Technical debt / postponed: invoice reconciliation, indexing/standalone receipts, deployment
load tests, learned reranking and all agent/execution milestones.
