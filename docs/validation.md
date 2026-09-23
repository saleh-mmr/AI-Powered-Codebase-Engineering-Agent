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

Implemented persistence slice; Milestone 7 remains in progress. Local PostgreSQL
migration/drift and browser save/reload acceptance remain pending.

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
