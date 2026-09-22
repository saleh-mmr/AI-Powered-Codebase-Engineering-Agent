# Validation record

Milestones 1 and 2: the user reported completion after receiving their local
validation procedures. Those local results were not independently rerun here.

## Milestone 3

Implemented, with available checks passing. Full acceptance still requires the
user's Docker/infrastructure/browser checks or executed CI results.

Verified here:

- Ruff lint/formatting and strict mypy pass (49 application modules).
- Backend: 62 tests pass. Four infrastructure tests skip intentionally.
- Tests cover all earlier auth behavior; ownership across repository endpoints;
  CSRF; persisted queued jobs without a broker; duplicate URLs; quotas surviving
  deletion; worker duplicate delivery; lease takeover; cancellation fencing;
  transactional publication; dispatcher failure/recovery; retry exhaustion;
  unsafe URL/path rejection; archive expansion/storage/count limits; exclusions;
  GitHub response errors and pinned-commit download paths.
- Portable API/worker tests use the real ORM/service pipeline with SQLite and
  controlled GitHub responses. They do not verify PostgreSQL locking or transport.
- Frontend: TypeScript, ESLint, Prettier, 13 component tests, and production build pass.
- Repository UI tests cover authenticated import submission, errors/retry, escaped
  source rendering, reselecting files, and session-expiry handling.
- Alembic offline SQL generation reaches 0003_repository_imports.
- The upgrade patch is checked/applied against Milestone 2 and compared to final files.

Not executed here:

- Docker builds/startup and migration 0003 on real PostgreSQL/pgvector.
- ORM/migration drift check against PostgreSQL.
- Redis atomic-rate-limit integration and the real Celery queue roundtrip test.
- Live public GitHub import and worker restart/cancellation acceptance.
- Browser desktop/mobile/keyboard review; this environment lacks working Chromium.
- GitHub Actions itself. A workflow definition is not a CI run result.

See docs/milestone-3.md for commands and expected behavior. Its isolated integration
suite uses a dedicated *_test database and Redis DB 1; do not run the worker fixture
against application data. CI runs that suite with its own service containers.

Known upstream warnings remain: Starlette test-client httpx deprecation and its
AnyIO BlockingPortal alias. They are not suppressed. One narrow type-check exception
bridges redis-py's untyped generic command API; its Lua result is validated. Celery's
untyped task decorator is isolated at the worker entry point. No paid AI calls occur.
