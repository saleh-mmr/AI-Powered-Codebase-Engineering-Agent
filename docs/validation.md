# Validation record

Milestones 1–5: the user reported completion after receiving local validation
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

Implemented; local full-stack and live-model acceptance remain pending.

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
