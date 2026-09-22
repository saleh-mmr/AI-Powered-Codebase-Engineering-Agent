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
