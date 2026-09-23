# Milestone 6 — Grounded repository Q&A

## What we are building and why

Ask a question about an imported repository, retrieve its code, and receive a short
explanation with inspectable source references. Retrieval remains independently
usable. This is the first real generated-answer slice, building on Milestone 5.

Each answer consists of factual claims plus citation IDs. The backend checks those
IDs against the retrieved evidence and supplies trusted paths, line ranges and the
imported commit SHA. A valid citation does not establish factual correctness; use
the evaluation rubric and inspect the actual source.

## Scope and architecture

React → authenticated/CSRF-protected route → AnswerService → existing SearchService
→ bounded context → AnswerProvider → structured validation → citation validation →
React source links. Model calls are asynchronous, and database read transactions
are released before generation. There are no agent tools or execution privileges.

One question produces one response. The browser displays it until the panel closes
or the page reloads. Saved conversations, messages, durable runs, streaming and
reconnection remain in Milestone 7. This intentionally postpones those specification
tables/API routes together instead of creating incomplete persistence now.

Important final paths:

- backend/app/api/routes/answers.py — thin authenticated GET/POST endpoints.
- backend/app/schemas/answer.py — request, settings and response contracts.
- backend/app/services/answers.py — ownership, quotas, retrieval and generation flow.
- backend/app/generation/contracts.py — replaceable provider and validated outputs.
- backend/app/generation/context.py — prompt loading, size budgets, citation checks.
- backend/app/generation/prompts/grounded_v1.txt — versioned system instructions.
- backend/app/generation/openai.py and factory.py — provider transport/configuration.
- backend/app/core/config.py, logging.py and main.py — configuration and lifecycle.
- frontend/src/features/answers/api.ts — runtime-validated frontend API contract.
- frontend/src/features/answers/AnswerPanel.tsx — question/loading/error workflow.
- frontend/src/features/answers/GroundedAnswer.tsx — claims, citations and code.
- frontend/src/features/repositories/FileBrowser.tsx — feature integration.
- backend/app/evaluation/answers.py and backend/evaluation/answers/v1/cases.json.
- backend/tests/unit/test_generation.py, test_answer_evaluation.py and
  backend/tests/api/test_answers.py; frontend/tests/answers.test.tsx.

All changed paths are listed in docs/milestone-6-files.txt. The archive contains full
final code plus UPGRADE_FROM_MILESTONE_5.patch with every exact change.

No database tables, ORM models, relationships or indexes change. The migration head
remains 0005_hybrid_search. Existing source/search indexes work without rebuilding.
No package dependencies were added. HTTPX and Pydantic already cover this bounded
provider integration; a larger orchestration framework is not justified yet.

## Upgrade and start

Extract the Milestone 6 archive separately. Copy UPGRADE_FROM_MILESTONE_5.patch into
your existing repopilot-ai root. Preserve your .env, Git history and database volume.
From that existing project root:

```bash
git apply --check UPGRADE_FROM_MILESTONE_5.patch
git apply UPGRADE_FROM_MILESTONE_5.patch
```

Success means both commands finish without errors. If you changed affected files,
inspect the conflict and apply the corresponding final changes; do not force an
archive over your work. The patch has been checked against the exact M5 delivery.

Add the new entries from .env.example to your existing .env. Do not overwrite it.
Leave APP_ANSWERS_ENABLED=false initially; the existing search workflow stays free.
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

Expected: 0005_hybrid_search (head), no schema drift; healthy database/Redis/backend,
running worker/dispatcher/frontend and HTTP 200. No API key is needed in disabled
mode. If starting a fresh project, use README.md's .env setup instead of the patch.

Open http://localhost:3000, sign in, and open Browse files for an imported repository.
You should see 06 / Grounded answers and an Ask the repository panel below search.
The panel explains that answers are disabled until configured. Search still works.

## Enable real answers deliberately

The initial provider sends your question and retrieved code to OpenAI. It incurs
API charges. A keyword-based answer does not require enabling semantic embeddings.
In your root .env, set:

```dotenv
APP_ANSWERS_ENABLED=true
APP_ANSWER_MODEL=gpt-4.1-mini-2025-04-14
APP_ANSWER_MAX_OUTPUT_TOKENS=1200
APP_ANSWER_DAILY_REQUEST_LIMIT=100
APP_ANSWER_INPUT_PRICE_PER_MILLION=0.40
APP_ANSWER_OUTPUT_PRICE_PER_MILLION=1.60
```

Set APP_OPENAI_API_KEY to your own key in the same .env. Never put it in a VITE
variable, commit it, or paste it into logs. Missing/empty keys stop startup when
answers are enabled. These price values are configurable estimates, not invoices.
The model is a pinned baseline; compare quality before changing it. Use an exact
Responses-compatible snapshot and update both rates when changing the model.

From the project root:

```bash
docker compose up -d --force-recreate backend
```

Wait for backend health, then click Refresh answer settings or reload the browser.
The panel must show the configured model and cost disclosure. Other services do not
need restarting for an answer-only setting change. To change embedding settings as
well, follow the backend/worker restart instructions in docs/milestone-5.md.

A local/free provider adapter is postponed. The present zero-charge path is keyword
search with answers disabled; no canned answer is presented as real AI behavior.

## Manual acceptance: real end-to-end workflow

1. Open an imported Python repository. Build its static index if needed.
2. Prepare Keyword + symbols in Search the code and wait for completion.
3. Search an actual function name; inspect the retrieved code.
4. Under Ask the repository, use Keyword + symbols and ask how that function works.
5. Expect a loading state followed by an answer, an insufficient-evidence response,
   or a clear provider error. No partial/unvalidated model text is displayed.
6. Click C1 beside a claim. It should scroll to the matching source, with a path,
   line range and the same imported commit SHA. Compare the claim to that code.
7. Ask about behavior absent from the retrieved evidence. Inspect whether the model
   abstains; do not automatically count any citation as a correct answer.
8. Check narrow-screen layout, keyboard submission, visible focus and source scrolling.
9. Refresh. The answer disappears by design; repository/search data remains.
10. Sign in as another account. The original repository's answer/settings routes must
    return 404. The automated API tests cover this authorization boundary.

A successful real answer confirms integration, not overall model quality. Use the
fixture/rubric below for controlled evaluation. No live model request was made here.

## API contract

Browser paths use /api; direct FastAPI paths omit it.

| Method/path | Request | Success |
| --- | --- | --- |
| GET /api/repositories/{id}/answers | Owned session | 200 with enabled flags, configured model, output cap and price estimates |
| POST /api/repositories/{id}/answers | Owned session, CSRF, JSON question/mode | 200 typed answer, abstention or refusal |

Example POST body:

```json
{"question":"How does verify_access_token handle expiration?","mode":"keyword"}
```

Question length is 1–512 and must include a searchable term. Mode is keyword or
hybrid. Arbitrary system prompts, source content, provider keys or model choices
cannot be supplied in this API request. FastAPI /docs documents complete response
schemas. Important response fields: status, claims[{text,citation_ids}], evidence,
commit_sha, source_index_id, search_index_id, retrieval/embedding/prompt versions,
prompt hash, model, input/output usage, cost estimates and duration_ms.

401: missing/expired session. 403: invalid Origin/CSRF. 404: missing/foreign repository.
409: answers disabled or source/search index not ready. 422: invalid input/context
limit. 429: shared application quota. 502: invalid/citation/incomplete model output
or provider rejection. 503: timeout, provider/Redis/database unavailability. Errors
use the existing safe envelope with a request ID. Raw provider errors are omitted.

The total answer deadline is 60 seconds, the browser waits 65, and nginx waits 70.
The HTTPX provider has 30-second I/O timeouts. There is no automatic retry, including
no model-based JSON repair. Closing the panel aborts browser waiting, not guaranteed
provider execution or billing. Failed requests may consume quota and incur charges.

## Automated validation: no paid calls

From the project root:

```bash
cd backend
uv sync --frozen
uv run python -m app.embeddings.tokens
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
uv run python -m app.evaluation.answers --check
```

Expected: lint/types pass, 143 backend tests pass, and six real-infrastructure tests
skip unless opted in.
The fixture check prints valid_cases=8 and provider_calls=0. It checks source/context
budgets and labels, not answer quality. No API key is needed for these checks.
See docs/validation.md for the measured counts and unexecuted gates.

From the project root in another terminal:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm check
pnpm test
pnpm build
```

Expected: checks pass, 24 component tests pass, and dist/ is built. Existing tests
remain included. New tests cover working source anchors, escaped source, configuration
states, loading/repeated-submit prevention, abstention, refusal, provider errors and
session expiry. For real PostgreSQL/Redis/Celery tests, retain the dedicated *_test
database workflow in docs/milestone-5.md. Never run fixture tests on application data.

## Answer evaluation

The eight fixed-context cases isolate generation from retrieval. They include code
behavior, authorization, boundary conditions, irrelevant/empty context, malicious
comments and misleading comments. Each stores expected facts and forbidden claims.

Run paid evaluation only when you intentionally want to spend on model calls.
From the project root in Bash, with your key configured in .env:

```bash
set -a
. ./.env
set +a
export APP_ANSWERS_ENABLED=true
cd backend
uv run python -m app.evaluation.answers --allow-paid --output evaluation/answers/reports/baseline.json
```

The runner connects only to the model provider; it needs no running database or
Redis and sends only the bundled synthetic snippets. It makes at most seven calls;
the empty-context case does not call a model. CLI evaluation is outside the API's
Redis quotas, but has bounded inputs/outputs, sequential calls, 35-second per-case
deadlines and no retries. The explicit --allow-paid flag is required.

Success writes a JSON report with per-case status, claims, source, latency, usage,
cost estimates, citation validity and reproducibility metadata. A report may contain
provider errors: inspect errors before treating it as a quality baseline. Failures
with unknown usage can still be billed. No automated factual score is invented.

Review the report using docs/evaluation.md. Fill human correctness/groundedness/
citation-support grades separately. Compare only matching dataset hashes, and
record model, prompt hash, output cap and rates. This is a small development fixture,
not a held-out benchmark or an end-to-end retrieval measurement. Combined RAG and
real-repository held-out evaluation remain visible follow-up work.

## Common errors and important limits

- Panel missing: rebuild frontend, then open Browse files; inspect the 06 header.
- Disabled after changing .env: recreate backend and refresh answer settings.
- Startup requires APP_OPENAI_API_KEY: supply it privately or disable answers.
- Prepare search first: a static index alone is insufficient; prepare the selected
  keyword/hybrid search generation. Existing M5 generations can be reused.
- Provider configuration/model error: verify key access, account quota and exact
  model snapshot. The application intentionally suppresses raw provider bodies.
- Incomplete output: retry a narrower question; if necessary raise the server output
  cap deliberately (maximum 2000) and recreate backend. This can increase cost.
- Invalid source reference: answer rejected. Inspect evaluation behavior; do not
  remove validation or accept fabricated citations to make the demo succeed.
- No evidence: try an identifier or prepare hybrid search. Retrieval misses and
  insufficient evidence are normal outcomes that must remain visible.
- Rate limit: wait; daily counters can prevent requests for up to 24 hours.
- Lost answer after reload: persistence starts in M7; this is intentional.
- Two upstream Starlette/AnyIO test deprecation warnings are documented in validation.md.

## Milestone status

Completed: bounded grounded-answer API/provider, React Q&A, citation validation,
mocked failure tests and eight-case evaluation tooling/documentation.
Verified: see docs/validation.md for actual checks; local full-stack/live-model
acceptance is still required before proceeding to the next major milestone.
Next: Milestone 7 — conversations/messages, background runs, streaming/reconnection,
durable usage and the complete repository-understanding MVP experience.
Technical debt/postponed: local model adapter, held-out end-to-end RAG evaluation,
financial ledger/idempotent billing, stronger public-deployment abuse controls,
learned reranking, successful-import refresh and autonomous tools/execution.

Suggested commit: feat(answers): add grounded repository Q&A with validated citations
