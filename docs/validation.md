# Validation record

Milestones 1–3: the user reported completion after receiving local validation
procedures. Those local results were not independently rerun here.

## Milestone 4

Implemented; tool-run checks pass. Local real-infrastructure/browser acceptance
remains required before treating the milestone as fully accepted.

Verified here:

- Ruff lint and formatting; strict mypy (60 application modules).
- Backend: 87 tests pass; 4 infrastructure tests skip intentionally.
- Earlier authentication/import regression tests continue passing.
- New tests cover lexical scopes, decorators, signatures/docstrings, repeated names,
  exact source reconstruction, Unicode/CRLF, byte limits, empty/invalid source,
  explicit fallback, owner-scoped APIs, CSRF, duplicate delivery, dispatcher routing,
  cancellation, lease takeover, atomic rollback, cross-snapshot constraints,
  failed-generation preservation, persisted symbol links and cascading deletion.
- SQLite tests exercise real ORM/services but do not establish PostgreSQL lock semantics.
- Frontend: TypeScript, ESLint, Prettier, 16 component tests and production build.
- UI tests cover index submission with CSRF, action errors, diagnostics, source
  ranges and escaped untrusted chunk text, alongside earlier UI regressions.
- Offline inspection CLI and Alembic SQL generation through 0004_source_indexes.
- Upgrade patch applies to the exact delivered Milestone 3 and matches final files.

Not run here:

- Docker builds/startup, migration on real PostgreSQL, or live alembic check.
- Real Redis/Celery transport and PostgreSQL locking/constraints integration.
  The integration queue test now covers both import and indexing; CI is configured
  to run it, but no GitHub Actions run was observed here.
- Browser desktop/mobile/keyboard acceptance (no working browser runtime here).

Follow docs/milestone-4.md, including its isolated infrastructure gate. No paid AI
calls are used. Two existing upstream warnings remain visible: Starlette's httpx
test-client deprecation and its AnyIO BlockingPortal alias. Narrow type exceptions
remain isolated at Redis's generic command API and Celery's untyped task decorators.
