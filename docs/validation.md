# Validation record

Milestones 1–6: the user reported completion after receiving local validation
procedures. Those local results were not independently rerun here.

## Milestone 5

Implemented; available checks passed. The user subsequently reported local
completion; those database/browser/benchmark results were not independently rerun here.

Verified here:

- Ruff lint/format and strict mypy pass (84 application modules).
- Backend: 110 tests pass; six real-infrastructure tests skip without opt-in.
- Previous auth/import/index tests remain passing. New tests exercise token splits,
  Unicode preservation, malformed provider responses, ordering/dimensions/usage,
  safe errors, rank fusion, metric calculations, serialized context budgets,
  authorized preparation/query behavior, free mode, budget preflight, resumable
  failures, reservation preservation, cancellation and cascading cleanup.
- Portable API/worker tests use SQLite and controlled providers/candidate lists.
  They do not verify PostgreSQL full-text/vector SQL or semantic relevance.
- Frontend: TypeScript/ESLint/Prettier, 19 component tests and production build.
- New UI tests cover CSRF queries, free/semantic separation, channel ranks,
  immutable provenance, escaped source, empty results and provider errors.
- Tokenizer asset load and benchmark CLI argument handling work.
- Offline dataset validation confirms all 14 relevance-label sets resolve; the
  corpus produces 26 source chunks and 1236 embedding-input tokens, without API calls.
- Offline Alembic SQL generation reaches 0005_hybrid_search.
- Upgrade patch is applied to the exact Milestone 4 archive and compared with final files.

Not executed here:

- Docker image builds/startup and migration/drift checks on real PostgreSQL.
- Native full-text/pgvector search, the fixture benchmark, Redis/Celery integration,
  or an actual GitHub Actions run. Tests/workflow definitions are not run evidence.
- Live OpenAI calls or semantic quality measurements. No paid calls were made.
- Desktop/mobile/keyboard browser acceptance; no working browser runtime here.

No benchmark scores are invented or substituted with mock-vector results. Use
real PostgreSQL and the versioned benchmark instructions in docs/milestone-5.md;
semantic evaluation requires explicit --allow-paid. CI is configured to publish
its real keyword report as an artifact, once it runs.

Two pre-existing upstream test warnings remain visible: Starlette's httpx test-client
deprecation and AnyIO BlockingPortal alias. Narrow typing bridges remain in the
Redis generic-command API and Celery decorators. EmbeddingVector's TypeEngine[Any]
is the SQLAlchemy dialect adapter's generic return type, not unvalidated API data.


## Milestone 6

Implemented; the user subsequently reported local completion. Those live-provider
and full-stack results were not independently rerun here.

Verified here:

- Ruff lint/format and strict mypy pass (93 application modules).
- Backend: 143 tests pass; six infrastructure tests skip without opt-in.
- New tests cover structured provider transport, no storage/tools, model/usage
  validation, incomplete output, refusal, malformed JSON, safe provider errors,
  no automatic retries, context limits, citation IDs, owner/CSRF checks, disabled
  mode, request validation, no-evidence abstention, shared deployment quota and
  released database transactions before generation.
- Existing authentication/import/index/retrieval regression tests remain passing.
- Frontend: TypeScript/ESLint/Prettier checks, 24 component tests and production build.
- The fixed-context fixture validates all eight cases without a model call. Its
  runner preserves invalid-citation failures and usage, and leaves human grades null.
- The app factory/lifespan starts in the API tests with default generation disabled.
- No database schema or dependency lockfiles changed; head remains 0005_hybrid_search.
- The M6 upgrade patch is checked and applied against the exact M5 archive, then
  all final packaged source files are compared with the applied result.

Not executed here: real PostgreSQL/Redis/Celery and Docker startup, actual CI,
manual browser acceptance, live Responses API calls or human-rated answer evaluation.
No paid calls were made; mocked contract tests are not evidence of live model quality.
Two existing upstream Starlette/AnyIO warnings remain as described above.


## Milestone 7A

Implemented persistence slice; the user subsequently reported completion. These
local results were not independently rerun here. Milestone 7 remains in progress.

Verified here:

- Ruff lint/format and strict mypy pass (98 application modules).
- Backend: 151 tests pass; seven infrastructure tests skip without opt-in.
- Eight new API cases cover saved question/answer pairs, owner/CSRF checks, provider
  and citation failures without partial writes, paged ordering, rollback of counter
  allocation on insert failure, composite owner constraint, delete cascades,
  full-conversation rejection and deletion during generation.
- Saved evidence remains readable after source-index deletion. History reads do
  not invoke the provider. No database transaction spans model I/O in the fake-provider test.
- Frontend: TypeScript/ESLint/Prettier, 28 component tests and production build pass.
- New UI tests cover create/save/reopen after remount without another model request,
  one citation target per saved answer, explicit deletion confirmation, pagination,
  read-only history retry and session expiry.
- Offline Alembic SQL generation reaches 0006_conversations and includes owner,
  ordering/role/token/payload constraints and the supporting indexes.
- The upgrade patch is applied to the exact Milestone 6 archive and the applied
  files are compared with the final source before packaging.

Not executed here: actual PostgreSQL migration/drift or concurrent append test,
Redis/Celery checks, Docker startup/builds, real browser acceptance or an actual CI
run. These gates are documented in milestone-7a.md. No paid model calls were made;
provider behavior/prompt/evaluation are unchanged from Milestone 6. The existing
two upstream test deprecation warnings remain visible and explained above.

The migration and concurrent-publication test are defined, not claimed as passed
against a real PostgreSQL server. No background answer recovery, model history or
streaming is claimed for 7A.


## Milestone 7B

Implemented background execution slice; the user subsequently reported completion.
Those local results were not independently rerun here.

Verified here:

- Ruff lint/format and strict mypy pass (106 application modules).
- Backend: 162 tests pass; seven infrastructure tests skip without opt-in.
- New cases cover idempotent replay/conflicts, single active runs, atomic transcript
  publication, duplicate delivery, cancellation before/during generation, safe
  failures, owner/CSRF checks, configuration/source guards and dispatcher expiry.
- Frontend: TypeScript/ESLint/Prettier, 31 component tests and production build pass.
- UI cases cover reload without resubmission, cancellation, reuse of the same request
  key after an uncertain response, and known versus unknown usage.
- Offline Alembic SQL generation reaches 0007_answer_runs.
- The upgrade patch is checked and applied against the exact 7A archive; all applied
  source files are compared against the final source before packaging.

Not executed here: real PostgreSQL migration/drift and concurrency, Redis/Celery
roundtrip, Docker builds/startup, browser acceptance or actual CI. The existing
worker integration test now includes a mocked-provider answer run but remains one
of the seven skipped infrastructure tests. No paid provider calls were made.
Two existing upstream Starlette/AnyIO deprecation warnings remain.

Follow milestone-7b.md for infrastructure tests and manual acceptance. Polling is
implemented; SSE replay, conversation context and full per-call usage receipts
remain for 7C. Cancellation fences publication but cannot guarantee refund or
termination of an already accepted remote provider call.


## Milestone 7C1

Implemented bounded conversation-context slice; local full-stack acceptance pending.

Verified here:

- Ruff lint/format and strict mypy pass (108 application modules).
- Backend: 173 tests passed, seven infrastructure tests skipped; two existing
  upstream Starlette/AnyIO deprecation warnings remain.
- New tests cover frozen snapshots despite later message changes, idempotent replay,
  source/conversation/abstention boundaries, malformed stored history rejection,
  stateless compatibility, complete-pair budgets, current-evidence priority,
  malicious dialogue remaining data, and citation IDs restricted to current evidence.
- Frontend: TypeScript/ESLint/Prettier, 32 component tests and production build pass.
  New checks verify old-snapshot defaults and visible history provenance.
- Offline SQL generation reaches 0008_answer_history. The first invocation lacked
  APP_DATABASE_URL; rerunning with a dummy offline URL succeeded without connecting.
- Free fixture validation: original eight cases plus four follow-up cases, zero
  provider calls. Prompt version is now grounded-v2. No live quality score is claimed.
- The upgrade patch is checked and applied to the exact 7B archive; every applied
  source file is compared with the packaged final source.

Not executed here: real PostgreSQL migration/drift/locking, Redis/Celery roundtrip,
Docker builds/startup, browser acceptance, actual CI or paid model evaluation.
Mock tests prove application behavior, not resistance of the live model to prompt
injection or factual accuracy. The 7C1 guide provides the remaining validation gates.
Streaming/SSE replay and fuller per-call usage receipts remain 7C2/7C3.
