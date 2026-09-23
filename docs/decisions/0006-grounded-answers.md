# ADR 0006 — Bounded grounded answers before persistent chat

Status: accepted for Milestone 6.

## Context

We already have independently inspectable retrieval. Now we need an end-to-end
question → evidence → explanation experience, without mixing model orchestration
into route handlers or prematurely implementing agent execution.

## Decision

Add a single-turn, asynchronous answer service and an independent generation
provider protocol. Reuse the existing search service; keep lexical/vector ranking
unchanged. A model receives a bounded JSON data object and a versioned instruction
file. It returns typed claims with citation IDs. Resolve evidence metadata from
retrieval, never from model-generated paths or line numbers. Reject unknown or
repeated citation IDs and invalid answer structures. No retrieval evidence means
no generation call. Model refusal and insufficient evidence are explicit outcomes.

The initial adapter uses HTTPX already in the project, with OpenAI Responses and
strict structured outputs. No SDK/orchestration dependency is needed for this one
request. The default is pinned gpt-4.1-mini-2025-04-14: a small non-reasoning baseline
with structured outputs, not a claim that it is the latest or best coding model.
Model selection remains an evaluation decision. Changing the configured model also
requires updating price estimates and checking adapter compatibility; use exact
snapshot IDs because responses are checked against the requested model. A local
provider can implement AnswerProvider, but its runtime/adapter is postponed.

Generation defaults off. It requires an operator-configured key and an explicit
user question. Keyword retrieval does not require embeddings, but its generated
answer still incurs model cost. Credentials are never part of the prompt.

Return answers without persistence in this milestone. The API path is temporarily
POST /repositories/{id}/answers; the spec's conversations/messages tables and
conversation-message API are introduced together in Milestone 7. No migration is
needed now, and reload loses the answer. Do not pretend this is a durable chat/run.

## Tradeoffs and safeguards

- A single asynchronous request is simpler for a first answer. It occupies an HTTP
  connection but does not block the event loop or retain a DB connection while
  generating. It has a 60-second total deadline. Background execution, durable
  conversation/run states, streaming and reconnection belong to Milestone 7.
- Prompts alone cannot guarantee injection resistance. The model has no tools,
  execution permissions, credentials or external browsing. Source and output are
  rendered as text. Citation membership is a structural guarantee, not entailment.
- There is no automatic paid retry. Ambiguous failure can cost money, including
  a browser disconnect. Accepted usage is logged even before citation rejection;
  malformed/incomplete/transport failures can have unknown usage. Durable accounting
  and idempotent submissions are not yet implemented.
- Redis limits five attempts/minute/user, thirty/day/user and one hundred/day across
  the deployment by default. These are expiring counters, not a financial ledger.
  Redis resets and multiple deployments can reset/multiply caps. Public paid access
  still requires stronger registration controls, financial enforcement and review.
- At most eight evidence chunks, 6000 estimated context tokens, 64 KiB serialized
  question/evidence, 8000 estimated instruction+input tokens and 1200 output tokens
  by default. cl100k is a size estimate for generation, not an exact billing count.
- The response uses store=false. That disables application response storage at the
  provider; it does not promise zero provider retention. Review provider data terms
  before sending source. Our application does not persist question/answer bodies.

## Evaluation

Use the eight-case fixed-context dataset to isolate generation from retrieval.
Check status behavior/citation IDs automatically and review factual correctness,
groundedness and citation support against expected facts. Keep missing human grades
null; mock tests are not a live quality score. Existing retrieval evaluation remains
independent. Combined retrieval-to-answer evaluation is a visible next step.

## Official references checked during implementation

- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/models/gpt-4.1-mini

Structured output can still be refused or incomplete. The adapter handles those
cases and independently validates returned JSON. Default configurable estimates are
$0.40/million input and $1.60/million output tokens; confirm current billing separately.
