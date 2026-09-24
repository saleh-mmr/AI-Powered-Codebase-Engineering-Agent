# ADR 0010: durable lifecycle events before provider token streaming

Status: accepted for Milestone 7C2A.

Polling current status can miss transitions between requests. Browser disconnects
must not restart paid generation. Establish a replayable observation channel before
adding provisional model output.

Store compact lifecycle events in PostgreSQL with a per-run composite primary key.
The transition's UPDATE obtains the run row lock; append_state allocates the next
sequence while that lock is held. State and event commit together, including final
messages/usage for completion. Failed event insertion rolls back publication. No
new broker or distributed cache data model is needed. Queue retries do not append
another event because the queued→running claim is conditional.

Use GET /answer-runs/{id}/events over SSE with Last-Event-ID or ?after. A short-lived
reader reauthenticates and authorizes each poll, closes its DB session before yielding,
and sends only bounded metadata. Heartbeats plus reconnect frames avoid idle proxy
timeouts; the existing Nginx configuration already disables proxy buffering. Native
EventSource cannot send the required application header, so React uses fetch with a
small bounded SSE decoder and AbortSignal. Reconnects are read-only, use backoff, and
coexist with slower polling. An interrupted stream is not a failed answer run.

At most three lifecycle events occur under the current state machine: queued,
running, terminal; queued cancellation/expiry can have two. The database check and
client schema explicitly enforce this bound. Future token/stage events require a
versioned protocol/schema change; do not put arbitrary deltas into this small table
without reconsidering storage, retention, ordering and backpressure.

Backfill one current-state entry for existing runs. Do not claim it reconstructs
past transitions. The stream logs its duration separately from HTTP header latency.
Per-user connection admission limits bound normal abuse; these are not a global
concurrency gate. Database polling is sufficient for a portfolio MVP; measure load
before adding Redis fanout. Seven infrastructure checks and manual proxy/reconnect
acceptance remain explicit gates. The spec's token-by-token requirement is still
open for 7C2B; this slice streams real lifecycle transitions, never fake token output.
