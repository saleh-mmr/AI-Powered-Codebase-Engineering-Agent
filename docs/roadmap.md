# Implementation roadmap

Source requirements: project-specification.md. The user selected React; ADR 0001
records the React + TypeScript + Vite change from the proposed Next.js frontend.

1. Runnable foundation — implemented, awaiting full Compose/browser validation.
2. Authentication and ownership — users, secure sessions, CSRF, protected dashboard.
3. Public repository import — GitHub integration, Celery/Redis, ownership, job states.
4. Python indexing and source browsing — AST chunks, immutable snapshot generations.
5. Hybrid search and benchmark — vector/lexical/symbol retrieval, Recall@K and MRR.
6. Grounded Q&A — provider interfaces, context construction, validated citations.
7. Streaming MVP — background runs, SSE recovery, usage tracking, complete UI states.
8. Read-only investigation agent — typed tools, bounded loops, action timeline.
9. Plans and patch proposals — pinned base, safe patch application, diff inspection.
10. Isolated execution — separate security boundary, curated test environments.
11. Bounded repair loop and coding benchmark.
12. Extensions individually: TypeScript, OAuth/private repositories, reranking,
    incremental indexing, PR review, deployment and deeper observability.

Milestones 1–7 deliver the initial repository-understanding MVP. Evaluation starts
with retrieval, background jobs start with import, and authorization starts before
user repositories. No major milestone advances without a clear validation gate.

Postponed from Milestone 1: authentication, business ORM tables, React Query,
Tailwind/shadcn, routing, Redis, workers, AI, repository import and code execution.
These are intentionally absent, not stub implementations.
