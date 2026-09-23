# ADR 0007 — Persistent conversations before background answer runs

Status: accepted for Milestone 7A. Milestone 7 is not complete.

## Decision and rationale

Introduce the specification's conversations and messages tables, with a typed
transcript API and React conversation workspace. A conversation is a saved collection
of independently grounded questions; prior messages are not yet model context.
Make that limitation explicit in the product. Keep the existing temporary-answer
API compatible and available. No new library or service is needed.

ConversationService invokes the existing AnswerService and persists the validated
question/answer pair in one transaction after generation. A short conditional UPDATE
allocates two adjacent message positions, then both rows are inserted before commit.
Concurrent completions serialize on this update and are ordered by publication,
not arrival time. No DB connection or row lock is retained across model generation.
A failed provider/citation validation leaves no messages. Conversation deletion
before publication wins: the request must not recreate history.

Each conversation carries user_id and repository_id. A composite foreign key to
repositories(id,user_id) enforces matching ownership, backed by a new repository
unique constraint. Application queries additionally authorize every resource.
Cascading deletion follows user → repository → conversation → messages.

Messages store role/content plus a turn ID and ordered position. Assistant messages
also contain a server-produced AnswerResponse JSON snapshot. This retains exact
source evidence, commit/index IDs, model/prompt identity and known usage estimates.
There are no foreign keys to source chunks: a saved answer remains inspectable if
an old index is removed. Never accept a client-authored answer snapshot as proof of
grounding. Both JSON creation and validation occur on the server.

JSON is a payload snapshot, not a searchable analytics table; no JSON index is
added. Some source text is duplicated, intentionally trading storage for provenance
and independent transcript lifetime. Keep at most 100 conversations/repository,
100 turns/conversation and twenty messages/page. The composite conversation/position
unique index also serves bounded transcript reads. Measure storage before changing
these bounds. The list returns at most the repository's 100 conversations.

User token_count is null because the model's reported input count includes prompts
and source, not merely the question. Assistant token_count records provider output
usage (including structured JSON), or null if no model was called. Full input/output
usage and cost estimates are retained in answer JSON. This is not a billing ledger.

## Remaining limitations and next step

Generation still uses M6's bounded HTTP request. An interruption can leave either
no saved turn or a committed turn whose response did not reach the browser. The UI
provides a read-only Refresh history action; inspect it before resubmitting. There
is no automatic paid retry, idempotency key, durable pending question or recovery
claim. A DB failure after generation can consume provider cost without saving an
answer. A capacity race can similarly reject publication after generation.

Milestone 7B will introduce durable answer runs, idempotent submission, bounded
history/context policy, worker states, usage accounting and streaming/reconnect.
Do not reuse the existing import job retry policy blindly for paid generation:
unknown provider outcomes require an explicit duplicate-spend policy. These are
planned features, not empty stubs in this milestone.

This split keeps the migration/transcript slice independently testable before
changing execution semantics. Before 7B, apply the migration, verify saved answers
survive a reload, check ownership/deletion and run the supplied database tests.
