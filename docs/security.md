# Security model — Milestone 2

Users and sessions are implemented. No repository imports, model calls, or code
execution are available. Public deployment is not part of this milestone.

## Identity and writes

- Argon2id password hashes, 15–128 character new passphrases, no password trimming.
- Random session cookies; only their SHA-256 digests are stored in PostgreSQL.
- HttpOnly, host-only, SameSite=Lax cookies; production settings require Secure/HTTPS.
- Login rotates the browser session; logout revokes it; expiry is checked server-side.
- Every authenticated endpoint derives its user from the session. Frontend IDs do
  not establish authority. Per-repository checks arrive with repository resources.
- Exact Origin plus a custom request header and JSON content type protect auth
  writes. Authenticated writes also require a session-bound CSRF proof. No permissive CORS.
- Validation errors omit raw values, preventing password reflection.
- Login failures use the same message for unknown accounts and wrong passwords.
- Duplicate registration returns 409; this exposes account-registration status.
  Email verification and privacy-preserving registration are postponed together.

## Resource limits and deployment boundary

A bounded process-local throttle limits valid auth attempts by normalized email
and network peer. It resets on restart and is not shared between workers. Behind
nginx it conservatively treats the proxy as the peer; it does not trust arbitrary
forwarded-IP headers. Introduce Redis-backed limits and explicit trusted-proxy
configuration before multi-worker/public deployment. Password hashing is offloaded
from the event loop, with at most two concurrent Argon2 operations per process.

Compose binds ports to loopback. API and frontend containers run as non-root. The
frontend sends a content security policy. Secrets stay server-side; `.env*` files
are excluded from Docker contexts and `.env` is excluded from Git. Existing DB
credentials must be retained during upgrades.

The local PostgreSQL provisioning account is not a least-privilege production
runtime account. Before public deployment, separate migration/runtime roles,
provision TLS, add shared abuse controls, email verification/account recovery,
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

No arbitrary commands or imported code are executed. Future imports require
URL/path validation and resource limits; execution requires an independently
reviewed isolation boundary.

See ADR 0002 for the implementation choices and remaining tradeoffs.
