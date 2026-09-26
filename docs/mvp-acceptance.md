# Milestone 7 final MVP acceptance

Run this gate before Milestone 8. This is a procedure, not a claim that checks were run.
Keep actual evidence (commit, date, commands, counts and evaluation reports) with the
release. Use a small public Python repository you are authorized to send to the configured
provider. Existing API rate and cost limits still apply. Do not use private secrets as fixtures.

| Gate | Action | Expected result |
| --- | --- | --- |
| Startup/migration | Follow milestone-7c3.md startup; check /health/live and /health/ready | HTTP 200, migration 0011, healthy stack, no schema drift |
| Authentication | Register, log out/in, reload; attempt a write without CSRF | Session restored safely; invalid write rejected |
| Public import | Import a small public Python repository; observe progress; reopen | Durable terminal state, pinned commit and readable source |
| Index and search | Build source and keyword search indexes; inspect matching symbol/file | Grounded line ranges and independent search results; no paid call |
| Retrieval evaluation | Run docs/milestone-5.md PostgreSQL benchmark | Persist real Recall@K/MRR report; inspect failures, never use mock vectors as quality evidence |
| Grounded answer | Enable configured paid answers, prepare search, create conversation, ask about a function | Provisional label while streaming; final validated citations open matching source snapshot |
| Conversation recovery | Reload, reopen, ask a bounded follow-up | Saved turns retained; new claims cite current evidence; history cap enforced |
| Run recovery | Close/reopen view while running; refresh status | Same run and lifecycle replay; no duplicate generation |
| Cancellation | Cancel queued run, then a running run | No publication after cancellation; receipt may arrive late for an in-flight call |
| Accounting | Expand receipts and refresh after terminal state; optionally run hybrid | Generation/query embedding separate; known subtotal excludes unknown attempts |
| Ownership | Use a second account to request the first account's conversation/run/usage IDs | 404 with no evidence or usage leakage |
| Failure recovery | Stop worker, queue an answer, restart; stop Redis and inspect readiness | Queued work recovers; errors remain understandable; no silent fallback |
| UI | Check keyboard-only operation and narrow viewport; offline/error/retry states | Accessible controls, readable code, escaped draft content, no hidden reasoning |
| Persistence | Restart Compose without removing volumes, reopen saved work | Source/transcript/run/receipts retained |
| Cleanup | Delete conversation/repository; attempt old URLs | Children removed, stale URLs rejected, no late result resurrection |
| Infrastructure tests | Dedicated *_test DB and opt-in tests from milestone-7a.md | Seven real PostgreSQL/Redis/Celery integration tests pass |
| Quality/build | Backend/frontend commands in milestone-7c3.md; CI on your branch | Lint/types/tests/build pass; actual CI report retained |
| AI evaluation | Follow docs/evaluation.md; opt into paid evaluation only when ready | Versioned report includes real metrics, human grading and failures, latency/tokens/cost |

No live evaluation scores or full-stack acceptance are inferred from unit tests. Inspect
citation correctness and answer relevance, not merely whether the endpoint returned 200.
Compare streaming and buffered evaluation using the same fixture/model/prompt configuration.

Acceptance record (fill after execution):
- Commit and environment:
- Startup/migration and integration results:
- Browser workflows and remaining defects:
- Retrieval/model report paths and review:
- Decision: accept Milestone 7 / fix listed defects before proceeding.

Current environment limitation: Docker/PostgreSQL binaries and a configured live stack
were unavailable during this implementation. See validation.md for actual automated evidence.
