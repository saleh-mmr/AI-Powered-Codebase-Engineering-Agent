# ADR 0001: React client and modular FastAPI backend

Status: Accepted for Milestone 1.

The user selected React for the frontend. We use React + TypeScript + Vite instead
of the originally proposed Next.js application. Server rendering is not necessary
for this authenticated repository workspace. FastAPI owns business rules, data
access, authorization, and API contracts. Vite supplies the local frontend server
and static production build; nginx serves the built UI and proxies `/api/`.

The browser uses same-origin relative API URLs. In development Vite strips `/api`
and forwards to FastAPI; the Compose nginx service applies the same mapping.
This avoids unnecessary CORS configuration and establishes the route for later
cookie-based authentication. CSRF protection remains necessary in that milestone.
No browser environment variables contain secrets. API_PROXY_TARGET is read only
by the Vite configuration. Backend settings are loaded centrally and validated.

The backend starts as a modular monolith. Jobs will share this package while
running in a separate process. Routes delegate dependency checks to the database
module. Future business operations will use service and data-access modules.

PostgreSQL with pgvector is retained from the specification. Alembic owns schema
changes. Revision 0001 enables the extension only: no business ORM models or
relationships exist yet. Its downgrade retains the extension because extensions
may be shared by other schemas. Application startup does not create tables.

Liveness asks whether the process responds. Readiness additionally checks its
database and vector extension. The process can remain alive when its database is
unavailable. Do not restart it repeatedly just because a dependency is down.

Python dependencies use uv; frontend dependencies use pnpm. Lockfiles make installs
reproducible. pytest and Vitest cover failure paths without paid AI calls. Ruff
handles both formatting and linting; mypy and TypeScript check types. Playwright,
React Query, Tailwind/shadcn, authentication, Redis, and workers are introduced when
needed. Milestone 1 uses a small CSS file and native fetch to avoid unused layers.
