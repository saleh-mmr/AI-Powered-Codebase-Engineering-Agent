# ADR 0008 — Durable answer runs with conservative paid-work recovery

Status: accepted for Milestone 7B. Streaming and bounded model history remain 7C.

Named conversations submit durable AnswerRun records before dispatching work to the
existing Celery worker. The dispatcher polls committed queued records and republishes
unclaimed work after thirty seconds if needed. The broker is transport; PostgreSQL
is the source of truth. The API returns 202 immediately for a new run, 200 for replay.
The previous synchronous message/temporary-answer endpoints remain compatible.

Each request includes a client-generated UUID request_key scoped to a conversation.
A stored hash covers the validated question and mode. Reusing a key with the same
payload returns the original run, including a terminal run; reusing it for a different
payload returns 409. Replays do not consume another submission quota. A conversation
row lock plus a unique request constraint serialize acceptance; a partial unique
index permits only one queued/running background run per conversation. This does not
claim exactly-once external billing or govern the legacy synchronous route.

Workers atomically claim only queued runs. Duplicate deliveries cannot claim running
or terminal work. A 180-second lease and random token fence publication. Completion
updates run state/known usage and inserts the question/answer pair in one transaction,
locking the conversation before the run to match cascade-delete lock ordering. There
is no database transaction across model I/O. The answer ID equals its durable run ID.

Unlike imports, a running answer is NEVER automatically reclaimed. After lease expiry,
the dispatcher marks it failed with answer_worker_lost. A provider may have accepted
the request before a crash; retrying automatically would risk duplicate spend. Users
can deliberately submit a new request after inspecting status. Queued work expires
after one hour if never claimed. Both timeouts require the dispatcher to be running.

Cancellation clears the token and prevents subsequent publication. It cannot guarantee
stopping a remote provider request or refunding its charge. Deleting a conversation
cascades to its runs; a late worker cannot recreate it. A successful cancellation may
race completion, in which case the API returns 409 and the UI refreshes status.

Submission records the source-index ID and a hash of model, output cap, price estimates,
prompt hash and retrieval version. A changed model configuration fails the worker
before generation. The answer service validates the retrieved source-index ID before
the generation call. In hybrid mode a query embedding may already have been billed
before source-change detection. Search-generation IDs are not separately pinned;
compatible rebuilds against the same source may still be selected.

Usage is explicit: not_started means no worker claim; unknown means an attempt began
but a full result was not committed; recorded means the completed answer's generation
tokens and combined retrieval/generation estimate were committed. Unknown is not zero.
This deliberately conservative classification can mark a configuration rejection as
unknown even when no model call occurred. Failed, cancelled, or crashed attempts are
not a complete financial ledger. Provider-side reconciliation and per-call receipts
remain future work. API-key values never enter hashes or records.

The React client polls durable status every two seconds while active and ten seconds
when idle. Reopening fetches server state; it does not resubmit. An uncertain HTTP
submission retains its key and payload in memory for an explicit safe retry. Reload
checks the server's recent runs; it does not persist source/questions in localStorage.
No automatic model retry is introduced. History reloads when completion is observed.

We intentionally separate transport streaming and conversation-context changes into
7C. Durable execution/cancellation need validation before adding event replay or
changing the evidence/prompt contract. No SSE, token stream, agent reasoning trace or
multi-turn memory is claimed for 7B. No new dependency or infrastructure service is needed.
