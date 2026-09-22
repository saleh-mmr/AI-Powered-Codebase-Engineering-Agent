# Security model — Milestone 3

Users, sessions, and bounded public repository imports are implemented. No model
calls or repository code execution are available. Public deployment is not part of this milestone.

## Identity and writes

- Argon2id password hashes, 15–128 character new passphrases, no password trimming.
- Random session cookies; only their SHA-256 digests are stored in PostgreSQL.
- HttpOnly, host-only, SameSite=Lax cookies; production settings require Secure/HTTPS.
- Login rotates the browser session; logout revokes it; expiry is checked server-side.
- Every authenticated endpoint derives its user from the session. Frontend IDs do
  not establish authority. Repository and file actions now enforce ownership in database queries.
- Exact Origin plus a custom request header and JSON content type protect auth
  writes. Authenticated writes also require a session-bound CSRF proof. No permissive CORS.
- Validation errors omit raw values, preventing password reflection.
- Login failures use the same message for unknown accounts and wrong passwords.
- Duplicate registration returns 409; this exposes account-registration status.
  Email verification and privacy-preserving registration are postponed together.

## Resource limits and deployment boundary

Authentication and import submissions use atomic shared Redis counters. Redis
failures fail closed; no process-local fallback is used in production code. Imports
are limited to five attempts/hour/user and twenty stored repositories/user. The
hourly counter survives deletion. Redis is configured with a bounded noeviction
policy and append-only persistence. Password hashing remains offloaded and bounded
to two concurrent Argon2 operations per process.

Repository URLs are restricted to public github.com roots. HTTP requests only target
api.github.com and codeload.github.com with bounded bodies and no redirects. Commit
metadata is validated, and archives are pinned to the resolved SHA. No files are
extracted to the host. Unsafe paths reject imports; links/special files, credential
filenames, binaries, vendor/generated files, and oversized files are skipped.
Expansion, entry count, retained content, parsing time, and overall runtime are capped.
Filename exclusions are not a complete secret scanner. Never assume a public repo
contains no secrets. Source text is displayed through React's escaped rendering.

Jobs use atomic claims and expiring lease tokens. Cancelled/stale workers cannot
publish. Successful file publication is transactional. Repository removal cascades
to jobs and files. Retries cannot execute repository content.

Compose binds ports to loopback. API and frontend containers run as non-root. The
frontend sends a content security policy. Secrets stay server-side; `.env*` files
are excluded from Docker contexts and `.env` is excluded from Git. Existing DB
credentials must be retained during upgrades.

The local PostgreSQL provisioning account is not a least-privilege production
runtime account. Before public deployment, separate migration/runtime roles,
provision TLS, review shared abuse controls, add email verification/account recovery,
review dependency/image versions and pin deployable image digests, and review
operational endpoint exposure. Session idle timeout and all-device logout are later.

## Logging and data handling

Structured logs contain request IDs, route templates, duration, status, and safe
exception types. They omit request bodies, query strings, full connection URLs,
passwords, session cookies, CSRF proofs, and repository content. No error tracker
receives these values. Errors include a request ID for correlation.

Expired session rows are deleted during session creation. Logout deletes the
current row immediately. Users own sessions through a cascading foreign key.
Application responses never serialize password hashes or token hashes.

No arbitrary commands or imported code are executed. The import worker has CPU,
memory/process limits and a read-only filesystem, but is trusted application code
with database access. It is not a code-execution sandbox. Executing repository
code will require an independent isolation boundary with no application secrets.

See ADR 0002 and ADR 0003 for implementation choices and remaining tradeoffs.


## Milestone 4 static indexing

AST parsing occurs only in the existing resource-limited worker; imported source
is never executed. The API only queues jobs and reads results. Parser node/scope,
file, generation and deadline budgets are enforced. The Python parser can allocate
before node-count checking, so worker memory limits remain necessary. This worker
has trusted service credentials and must never become the repository-code executor.

Every indexing route enforces session ownership, and every write enforces CSRF.
Repository locks and the unique-current index serialize starts; shared Redis limits
new attempts to five per minute per user. Conditional lease publication prevents
cancelled/expired workers publishing data. Composite foreign keys enforce snapshot,
parent-symbol and chunk-symbol consistency. Source is escaped React text. Logs omit
source, signatures and docstrings. Failed replacement attempts retain the prior
completed index. Imported repository text remains untrusted prompt input when RAG
is added; indexing does not make it trusted instructions.


## Milestone 5 retrieval and external embeddings

Keyword/symbol mode does not call a model. Semantic mode defaults off and requires
server configuration plus an explicit user preparation/search action. Source and
queries are sent only to the fixed OpenAI embedding endpoint; keys never reach the
frontend or source context. The UI discloses this data transfer and possible charges.
Provider redirects/proxy inheritance are disabled, responses are bounded/validated,
and raw provider bodies are excluded from error messages. Tokenizer assets are
cached during image build so read-only workers do not need a runtime asset download.

All retrieval/preparation endpoints enforce repository ownership; POST queries
require CSRF. SQL is parameterized, and all candidate channels are filtered to a
completed authorized generation. Partial preparation is never searched. Native
vectors and chunk links are tied to the same source snapshot by composite keys.
The database connection is released before waiting for query embeddings.

Preparation reserves tokens before external calls and retains uncertain reservations
through crashes/retries. Per-user rate limits and a 25-second query deadline bound
requests. They do not replace a global paid-deployment budget or prevent multiple-
account abuse. Public registration/spend enforcement remains a deployment gate.
Source text is rendered escaped and remains untrusted input for future RAG prompts.
Retrieval scores are not confidence probabilities or authorization decisions.
