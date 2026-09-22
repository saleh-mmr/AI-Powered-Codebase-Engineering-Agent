# ADR 0002: Session authentication and request authorization

Status: accepted for Milestone 2.

## Decision

Use email/password registration and opaque server-side sessions. GitHub OAuth is
later and will not replace resource-level authorization. API routes remain thin:
Pydantic validates requests, dependencies establish identity and CSRF policy,
AuthService handles registration/login/revocation, and AuthRepository issues queries.

Passwords use Argon2id through argon2-cffi with an explicit 64 MiB memory cost,
three iterations, and one lane. Hashing runs in a thread pool and a process-local
semaphore permits at most two concurrent password operations, bounding Argon2 memory
to roughly 128 MiB plus overhead. Unknown accounts verify against a dummy hash to
avoid an obvious fast path. Valid login rehashes passwords if parameters change.
New passwords are 15–128 characters; passwords are not trimmed or silently altered.

A session token contains 32 random bytes, encoded as 43 URL-safe characters. Only
its SHA-256 digest is stored in the database. Raw cookies are HttpOnly, host-only,
SameSite=Lax, with a bounded Max-Age; Secure is mandatory in production configuration.
No authentication token is placed in localStorage, URLs, response JSON, or logs.
Login rotates the current browser's session and revokes its old token. Logout deletes
that session immediately. Other devices remain signed in. Expiration is enforced
server-side on every authenticated request, with a fixed default 24-hour lifetime.
Expired rows are pruned when creating sessions; dedicated maintenance can follow.

State-changing auth endpoints require the configured exact Origin and a custom
X-RepoPilot-Request header, plus application/json. These controls also protect the
pre-authentication login and registration requests. There is no permissive CORS
policy. Authenticated writes additionally require an X-CSRF-Token proof derived
with HMAC-SHA256 from the current session token using a fixed, domain-separated
message. The proof is returned by /auth/me and login/register and kept in React
memory. It cannot be used as the session cookie. Constant-time comparison verifies
it. require_csrf also enforces the origin/custom-header checks so future writes
can reuse one dependency. CORS and SameSite alone are not the authorization boundary.

/auth/me obtains its user solely from the cookie-backed database session. Neither
query-string IDs nor X-User-ID headers establish identity. Repository ownership
queries will be added alongside repository resources in Milestone 3; this milestone
does not create unused repository tables or pretend to test nonexistent resources.

## Database

- users: UUID primary key; unique normalized lowercase email; display name;
  Argon2 password hash; creation timestamp.
- sessions: token-hash primary key; user_id foreign key with ON DELETE CASCADE;
  created_at and expires_at timestamps with timezone.
- One user can have many sessions. Explicit joins avoid accidental async lazy loads.
- The unique email constraint prevents concurrent duplicate registrations.
- Session indexes support per-user revocation and expiration cleanup.
- Migration 0002 depends on 0001. Its downgrade drops sessions and users and is
  destructive: use only with a deliberate data-loss decision.

Email is lowercased as an explicit account-identity policy. Do not independently
write users through another integration without preserving this normalization.
Duplicate registration returns 409 and can reveal registration status; consistent
login errors do not reveal which credential was wrong. Account verification and
privacy-preserving registration responses require an email delivery workflow later.

## Dependencies and scope

argon2-cffi supplies password hashing rather than custom cryptography. email-validator
supports Pydantic email parsing and normalization. aiosqlite is test-only and lets
API tests exercise the real ORM/service stack without Docker; PostgreSQL migration
and integration checks remain separate, required CI gates.

A bounded in-memory throttle allows five validly shaped attempts per normalized
email and forty per network peer in sixty seconds. It fails closed at its storage
cap. It is intentionally single-process, resets on restart, and is not sufficient
for a distributed public deployment. Behind nginx, peer limits aggregate traffic
under the proxy address; forwarded client-IP headers are not blindly trusted.
Redis-backed limits and explicit trusted-proxy configuration precede scale-out.

Not included: email verification, password reset, MFA, idle timeout, account editing,
all-device logout, OAuth, or public deployment. None of these are placeholder APIs.

References:
- https://argon2-cffi.readthedocs.io/en/stable/howto.html
- https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
