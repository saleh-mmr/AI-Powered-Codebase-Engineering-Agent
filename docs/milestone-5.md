# Milestone 5 — Hybrid retrieval and evaluation

We can now search indexed code independently of chat and inspect why each source
chunk was returned. This establishes the retrieval, provenance and measurement
boundary needed before grounded answer generation.

## What is implemented

- Free PostgreSQL keyword + symbol search.
- Optional OpenAI query/source embeddings, native pgvector storage and hybrid fusion.
- Background preparation with persisted progress, cancellation, resumable batches
  and conservative token reservations.
- Typed owner-scoped APIs and React search/results inspection.
- A 14-question, seven-file development dataset, metric functions and a runner using
  the real PostgreSQL retrieval implementation. No fabricated benchmark scores.

Existing imported files and AST indexes remain usable. You prepare a new search
generation from a completed index; no re-import or static reindex is required.

## Upgrade from Milestone 4

Extract the new archive separately. Copy UPGRADE_FROM_MILESTONE_4.patch into your
existing repopilot-ai root. Preserve .env, your database volume and Git history.
From that existing root:

```bash
git apply --check UPGRADE_FROM_MILESTONE_4.patch
git apply UPGRADE_FROM_MILESTONE_4.patch
```

The check must succeed. If local edits conflict, inspect those edits rather than
forcing replacement. Full final files are also included in the archive.

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

Expected: 0005_hybrid_search (head), no schema drift, healthy PostgreSQL/Redis/backend
and running worker/dispatcher/frontend. The Docker build downloads the tokenizer
asset once and stores it readably in the image; read-only workers do not download it.
No model key is required for the default free workflow.

## First usable search: no paid calls

1. Open http://localhost:3000 and sign in.
2. Open Browse files for an imported repository. If its static index is missing,
   click Build index and wait for completion.
3. In Search the code, leave Keyword + symbols (free) selected. Click Prepare
   selected search. Expect queued → running → completed and a stored-chunk count.
4. Enter an actual identifier from the repository, then a descriptive question.
   Click Search code. Expand a result and compare path, lines and source with the
   original file. The commit SHA must match the imported snapshot.
5. Inspect lexical/symbol ranks and fused score. Scores are ranking values, not
   probabilities. Context labels identify the chunks selected within the budget.
6. Refresh: preparation persists. Preparing the same completed mode reuses it.
7. Test an unrelated keyword: an empty result is valid. Test narrow-screen layout,
   keyboard controls, details expansion and long code scrolling.

This is a retrieval inspector, not a chatbot. No answers are generated yet.

## Optional semantic search and explicit cost

This is opt-in. It sends embedding input derived from repository source to OpenAI
when preparing, and query text when searching. Do not enable it for source you are
not permitted to send. No paid request was made while preparing this milestone.

In your existing root .env, set:

```dotenv
APP_EMBEDDINGS_ENABLED=true
APP_EMBEDDING_TOKEN_BUDGET=200000
APP_EMBEDDING_PRICE_PER_MILLION=0.02
```

Also set APP_OPENAI_API_KEY to your own API key in that file. Never put it in a
frontend/VITE variable, commit it, or paste it into logs. Enabling embeddings with
an absent/empty key fails configuration validation. Keep the key out of this guide.
From the project root:

```bash
docker compose up -d --force-recreate backend worker dispatcher
```

Select Hybrid + semantic, read the disclosure, and click Prepare selected search.
Wait for completion, then run the same queries. Results may show lexical, symbol
and vector contributions. Keyword mode remains available with its previous index.
A provider failure is shown explicitly rather than silently dropping semantic search.

The initial model is text-embedding-3-small, 1536 dimensions. The default price
estimate is $0.02/million input tokens: 200000 reserved tokens corresponds to an
estimated $0.004 preparation ceiling at that rate, excluding query calls and other
charges. Confirm current provider pricing. Estimates are not invoices.

Budget range: 1000–2000000 tokens/job. Preflight prevents starting calls when the
remaining source exceeds the budget. Raise the configured budget deliberately,
restart backend/worker/dispatcher, then retry the same job to resume completed
batches. Reservations for failed/uncertain calls remain consumed. Retries can repeat
a call accepted by the provider before a worker crash; exactly-once billing is not
claimed. Three semantic preparation starts per user/day bound casual retries.

A local model is a free API alternative but needs a separate validated adapter,
model runtime and tokenizer/profile. It is not included or faked in this milestone.
For zero external model spend now, keep embeddings disabled and use keyword mode.

## Architecture, files and migration

The flow is React → authorized API → durable search job → existing dispatcher/
Celery worker → PostgreSQL search documents. At query time, the service uses three
candidate channels, fuses ranks and constructs bounded context. Provider calls live
behind their own interface and do not appear in route handlers.

Important paths:

- backend/app/embeddings/provider.py, openai.py, factory.py, tokens.py
- backend/app/retrieval/contracts.py, text.py, postgres.py, ranking.py, context.py
- backend/app/models/search_index.py and backend/app/models/search.py
- backend/app/jobs/prepare_search.py
- backend/app/repositories/search.py
- backend/app/services/search_preparation.py and backend/app/services/search.py
- backend/app/schemas/search.py and backend/app/api/routes/search.py
- backend/migrations/versions/0005_hybrid_search.py
- frontend/src/features/search/api.ts, RepositorySearch.tsx, SearchResults.tsx
- backend/app/evaluation/retrieval.py, fixtures.py, recording.py, metrics.py
- backend/evaluation/retrieval/v1/cases.json and corpus/

The full exact path list is docs/milestone-5-files.txt. The upgrade patch identifies
every change; no application-code placeholders are used.

Migration 0005 adds search_indexes and search_documents. Composite foreign keys tie
search generations to their owned source indexes and documents to matching chunks.
A unique current-generation constraint serializes preparations; a unique generation/
chunk key prevents duplicate documents. Dispatch indexes support worker recovery.
The lexical GIN expression index accelerates full-text matching. Vectors use native
vector(1536); there is no approximate vector index yet. At these bounds, start with
exact filtered search and measure before adding ANN recall/operational tradeoffs.

The migration adds two supporting uniqueness constraints to existing source tables;
it does not rewrite existing source or accounts. Downgrading 0005 deletes search
indexes/documents but retains static indexes. Do not downgrade or delete volumes as
a routine troubleshooting step. Apply with Alembic and verify alembic check above.

## Why these retrieval decisions matter

Indexing strategy: retain the source chunks and provenance from Milestone 4, then
create versioned search documents. Lexical text includes identifiers plus split
snake/camel spelling. Embedding text includes path, symbol, signature and code.

Tokenization: cl100k_base for the initial provider; repository special-token strings
are ordinary data. Split large inputs into 4096-token parts, embed all parts, then
normalize their token-weighted mean. Original source chunks are never truncated.
The provider interface owns tokenizer/profile identity for future adapters.

Lexical retrieval uses PostgreSQL simple-config text search and ts_rank_cd. Symbol
retrieval uses exact identifier matching, including nested definitions. Vector
retrieval uses cosine distance within the selected complete generation. Each channel
contributes at most 30 candidates. RRF sums 1/(60 + rank), deduplicates chunks and
uses deterministic source ordering for ties. No learned reranker is added yet;
measure its value against this baseline first.

Context construction selects whole result chunks within a serialized-JSON token
budget, including citation metadata. Omitted chunks are reported. No prompt is
constructed yet. A future answer model may require a different tokenizer and must
reserve tokens for instructions/history/output. Source remains untrusted prompt
input; retrieval does not promote repository text to system instructions.

## Automated checks

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

The tokenizer command may download its public asset once on a host installation;
it never calls a model API. It should print that cl100k_base is cached and ready.
Expected: checks pass; 110 tests pass and 6 infrastructure tests skip without opt-in.
The new tests cover token preservation, provider validation, rank fusion, metrics,
context budgets, authorization, free mode, cost preflight, checkpoint recovery,
cancellation and cleanup. Test providers are deterministic fakes for behavior only.

From the project root in another terminal:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm check
pnpm test
pnpm build
```

Expected: checks pass, 19 component tests pass and dist/ is produced. UI tests cover
CSRF submissions, free/semantic separation, escaped sources, provenance, empty
results and provider errors. Browser/manual acceptance is still required.

## Real PostgreSQL, pgvector and queue validation

Use the dedicated repopilot_test database, not your application data. From the
project root with Compose infrastructure running, create it once:

```bash
docker compose exec postgres sh -c 'createdb -U "$POSTGRES_USER" repopilot_test'
```

If it already exists, keep it. In Bash from the project root:

```bash
set -a
. ./.env
set +a
export APP_DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/repopilot_test"
export APP_REDIS_URL=redis://127.0.0.1:6379/1
export APP_EMBEDDINGS_ENABLED=false
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run alembic check
RUN_DB_TESTS=1 RUN_QUEUE_TESTS=1 uv run pytest -m integration
```

Expected: all six infrastructure tests pass. Tests use real PostgreSQL full-text and
pgvector operators, fake vectors for transport/scoping checks, and real Redis/Celery
for import → indexing → search preparation. No paid provider is called. The fixture
benchmark regression gate is keyword Recall@5 ≥ 0.5; it is not a broad quality claim.
These tests are defined in CI but have not been executed in this tool environment.

## Run the retrieval benchmark

Keep the dedicated *_test environment from the preceding section. From backend/:

```bash
uv run python -m app.evaluation.retrieval --mode keyword --output evaluation/retrieval/reports/keyword.json
```

Expected: printed metric JSON and a report file with Recall@1/3/5/8, MRR@8, per-query
rankings, p50/p95 latency, hashes, pipeline/profile and token/cost information.
It compares lexical-only, symbol-only and their fusion using the same candidates.
The runner creates its own fixture account/repository and cleans them up. Its
synthetic commit marker is a corpus hash, not a real GitHub commit.

For a real semantic comparison, explicitly enable the configured provider in this
terminal and allow charges. From backend/ with your API key already loaded:

```bash
export APP_EMBEDDINGS_ENABLED=true
uv run python -m app.evaluation.retrieval --mode hybrid --allow-paid --output evaluation/retrieval/reports/hybrid.json
```

This adds vector-only and hybrid results, using one query embedding per question
for the channel comparisons. The command incurs real preparation/query costs.
Compare reports only when dataset and corpus hashes agree. See docs/evaluation.md
for interpretation and limitations. No quality numbers are supplied as measured
results because this environment did not run PostgreSQL or live semantic evaluation.
CI publishes the free keyword report as a downloadable artifact after its checks.

## API contracts

Browser paths include /api; internal FastAPI paths omit it. Every route checks
resource ownership. Writes and queries require the existing session/CSRF headers.

| Method/path | Success | Behavior |
| --- | --- | --- |
| GET /api/repositories/{id}/search | 200 | Latest preparation, available keyword/hybrid generations, semantic-enabled flag |
| POST /api/repositories/{id}/search/prepare | 202 or 200 | Body {"mode":"keyword"} or {"mode":"hybrid"}; queue/resume or reuse completed work |
| POST /api/repositories/{id}/search/cancel | 204 | Body {}; revoke queued/running preparation |
| POST /api/repositories/{id}/search/query | 200 | Typed ranked hits, provenance, bounded context and usage |

Example query body:

```json
{"query":"verify_access_token","mode":"keyword","top_k":8,"context_token_budget":6000}
```

Limits: query 512 characters, top_k 1–20, context budget 100–12000. Invalid input is
422, foreign/missing resources 404, missing preparation/disabled mode 409, CSRF 403,
expired session 401, application limits 429, provider/dependency failures 502/503.
Search has a 25-second service deadline; the browser waits up to 30 seconds.
Open http://localhost:8000/docs for complete schemas and response examples.

## Common errors and remaining risks

- No search controls: rebuild frontend and open Browse files.
- Build the static index first: complete Milestone 4's indexing before preparation.
- Queued indefinitely: check worker, dispatcher and Redis with docker compose logs.
- relation search_documents does not exist: apply migration 0005 using the new image.
- Tokenizer download failure: run python -m app.embeddings.tokens during setup with
  access to its public asset host; do not remove the image's tokenizer cache.
- Embeddings disabled/missing key: keep keyword mode or configure the opt-in values.
- Provider rate limit: wait before retrying; checkpointed batches are retained.
- Budget exhausted: review reservations, increase the server cap deliberately, or
  use keyword mode. A retry does not reset consumed budget.
- Search results are old: both source and search refer to a pinned imported commit;
  successful-import refresh remains postponed.
- An unrelated semantic query returns neighbors: nearest-neighbor retrieval is not
  answer correctness. Inspect sources; abstention policy is a later Q&A requirement.
- Public paid deployment: per-user limits do not prevent multiple-account abuse.
  Global spend enforcement and registration controls remain a deployment gate.

## Milestone status

Completed: retrieval implementation, migration, inspection UI, evaluation dataset/
runner, tests and upgrade documentation.
Verified here: docs/validation.md records exact available checks.
Next: local database/browser acceptance and benchmark, then grounded Q&A.
Postponed: learned reranking, local model adapter, ANN indexes, global paid-deployment
budget, held-out real-repository evaluation, answer generation and agents.

Suggested commit: feat(retrieval): add hybrid search and reproducible evaluation
