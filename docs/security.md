# Security model — foundation

This milestone has no users, repository imports, LLM calls, or code execution.
Health endpoints intentionally reveal no repository or user data and return a
generic 503 on dependency failure. Full URLs, exception messages, query strings,
request bodies, credentials, and repository content are not logged. JSON logs
include server-generated request IDs, route templates, duration, status, and
exception types. Deeper safe diagnostics will accompany feature-specific errors.

Compose binds published ports to loopback. Backend and frontend containers run
as non-root users. The frontend's static server sends a content security policy.
Secrets remain server-side; `.env` is ignored by Git and Docker build contexts.
Do not commit `.env`. The example password is only a local development example.

The local PostgreSQL account provisions the database and extension; it is not an
appropriate least-privilege production runtime account. Before public deployment,
separate migration and runtime roles, provision TLS, review image/dependency
updates, pin deployable image digests, add authentication, CSRF protections and
rate limits, and restrict operational endpoints and documentation as appropriate.

No automatic error tracker receives repository data. No arbitrary commands or
untrusted repository code are executed. Future imports need URL/path controls and
resource limits; execution requires a separately reviewed isolation boundary.

Application health failure logs intentionally omit raw exception text. Identify
requests using X-Request-ID, then inspect database reachability and migration state
with the documented commands. Never paste a connection URL containing credentials
into an issue or log message.
