# ADR 0003 — Public repository imports and durable jobs

Status: accepted for Milestone 3.

## Import mechanism

Use GitHub metadata and default-branch commit lookup, then download the commit's
archive from the fixed codeload.github.com host. This intentionally replaces the
specification's initial clone step: history and a mutable Git checkout are not
needed for repository understanding yet. Commit metadata is re-resolved on each
retry, so changed default branches are handled. HTTP redirects are not followed;
a moved URL produces an actionable error. Only public repositories are supported,
without GitHub tokens. Unauthenticated GitHub rate limits may prevent an import;
the application shows that error and requires a later user retry instead of
hammering the API. Network/5xx errors retry at most three worker attempts.

User input is limited to exact https://github.com/owner/repository URLs. No arbitrary
host, port, credentials, query, or branch path is accepted. Metadata from GitHub is
validated too. The HTTP client does not inherit environment proxy credentials.

No archive is extracted to the filesystem. A bounded gzip reader feeds tarfile in
streaming mode. Only regular, permitted UTF-8 text files are retained. Unsafe or
duplicate paths reject the import. Symlinks, hardlinks, special/sparse files,
unsupported/binary files, large individual files, vendor/build directories, LFS
pointer files, and common credential filenames are skipped. Filenames are not a
complete secret detector; public source files may already contain committed secrets.
No repository code is imported as Python, installed, executed, or rendered as HTML.

Limits: 10 MiB compressed download (configurable up to 50 MiB), 40 MiB expanded tar
stream including ignored content, 5,000 entries, 256 KiB per stored file, 10 MiB total
stored text, and a 15-second archive parsing deadline. The overall attempt deadline
is 90 seconds by default, capped at 120. The worker also has container CPU/memory/
process limits and Celery soft/hard deadlines of 150/170 seconds. This is a bounded
import worker, not the future untrusted-code execution sandbox.

## Durable state and delivery

PostgreSQL is authoritative. A repository and its queued import_job are committed
in one transaction. A separate dispatcher publishes eligible job IDs to Celery via
Redis every five seconds. A queued job can be republished after thirty seconds, so
broker loss between DB commit and delivery cannot permanently strand the request.
The job row serves as the outbox; there is no duplicate outbox schema.

Workers claim jobs with an atomic conditional UPDATE. A claim has a fresh UUID
lease token, a three-minute expiry, and an attempt counter. Duplicate delivery while
a valid claim is running does nothing. An expired claim may be taken over. Progress
and completion require the current lease token and unexpired lease, fencing old
workers. On the third lost worker, the dispatcher marks the job failed.

A successful publication stores files and repository commit metadata and marks the
job completed in one transaction. Failures cannot expose partial file collections.
Cancellation invalidates the claim immediately; an in-flight HTTP request can
continue until its bounded timeout, but cannot publish results. Removing a repository
cascades through jobs and files. Successful imports are immutable in this milestone;
refresh/reindex generations arrive with indexing. Retry accepts failed/cancelled jobs
only and records a new job. Each repository has one current job, enforced by a partial
unique index.

## Ownership and schema

repositories belongs to users; (user_id, source_key) is unique. import_jobs belongs
to repositories. repository_files has a composite foreign key to the job and its
repository, preventing mismatched ownership links. Unique (import_job_id, path)
prevents duplicate files. The job status has a database check constraint, and an
index supports dispatcher scans. Successful files include content hashes, sizes,
extension-based language labels, and the parent job's pinned commit metadata.
No AST symbols, chunks, embeddings, or search index exists yet.

Every list, detail, retry, cancel, delete, file-list, and file-content request scopes
the resource by the authenticated user. Foreign resources return 404. Writes also
require the existing CSRF dependency. SQL row locks serialize per-user repository
quotas under PostgreSQL. The application caps each user at twenty repositories and
five import attempts per hour. The Redis hourly key survives repository deletion.

## Redis and frontend

Authentication throttles now use an atomic Redis Lua script rather than process-local
state. Redis failures fail closed for protected auth/import submissions. A noeviction
memory policy avoids silently dropping throttle keys. Redis holds queue messages and
expiring counters; source code remains in PostgreSQL. Ports remain loopback-bound
for development. Proxy peer throttling remains conservative behind nginx; trusted
client-IP forwarding must be explicitly designed before a public deployment.

React uses bounded polling (two seconds while importing, slower when idle), typed
schemas validated with Zod, and separate form/card/file-browser components. Text is
escaped by React. A small basic source viewer is included now to make the import
vertical slice inspectable; symbol navigation and source-line citations remain later.
No AI provider is used or billed.

Dependencies: Celery for worker execution, Redis for queue/shared limits, httpx for
bounded async GitHub access, Zod for runtime validation of repository payloads.
No Git library, graph database, or additional model framework is introduced.

## Validation boundaries

Portable tests use the real SQLAlchemy/service pipeline with SQLite and fake GitHub
responses. They do not prove PostgreSQL row-lock semantics or Celery transport.
Separate integration tests require PostgreSQL/pgvector and Redis. The Celery test
uses an isolated queue and controlled archive while exercising real message delivery
and database persistence. A real public GitHub import is a separate manual acceptance
step, not an external network dependency of CI.

References:
- https://docs.github.com/en/rest/repos/repos#get-a-repository
- https://docs.github.com/en/rest/repos/contents#download-a-repository-archive-tar
- https://docs.celeryq.dev/en/stable/userguide/tasks.html
