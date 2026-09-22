# Validation record

Milestones 1–4: the user reported completion after receiving local validation
procedures. Those local results were not independently rerun here.

## Milestone 5

Implemented; available checks pass. Full acceptance still requires the supplied
local PostgreSQL/Redis/Celery, browser and retrieval benchmark procedures.

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
