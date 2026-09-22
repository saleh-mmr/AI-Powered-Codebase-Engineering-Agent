# ADR 0005 — Inspectable hybrid retrieval before answers

Status: accepted for Milestone 5.

## Decision and dependencies

Use PostgreSQL full-text search, existing symbol metadata, and pgvector cosine
similarity. Merge independently ranked candidates using reciprocal-rank fusion
(RRF). No orchestration framework or separate vector service is needed.

Two dependencies are added: pgvector's Python/SQLAlchemy adapter for native vector
storage, and tiktoken for the OpenAI embedding tokenizer and current context-budget
accounting. Existing HTTPX handles the small provider API surface, so an additional
OpenAI SDK is unnecessary here. A local model is a reasonable free alternative,
but requires a model download/runtime, its own tokenizer/profile and validation;
that adapter is postponed. Default keyword/symbol retrieval incurs no model cost.

The initial semantic adapter uses text-embedding-3-small with 1536 dimensions.
EmbeddingProvider owns tokenization, profile identity and batch calls; the rest of
the pipeline validates outputs and never accepts frontend-provided model names,
provider URLs or vectors. Supporting another vector dimension requires an explicit
schema/profile migration rather than mixing incompatible spaces. Test providers
exist only in tests and never masquerade as semantic search in the application.

## Preparation and storage

A search generation references a completed source index, not a mutable branch.
search_indexes records pipeline version, source commit, mode/provider profile,
status/lease, completed document count, token budget and usage. A partial unique
index permits one current preparation per repository. Old completed generations
remain readable for the same source; a changed source requires preparation again.

search_documents references both its search generation and source chunk through
composite foreign keys, preventing cross-snapshot associations. It stores lexical
text, embedding-input hash, token count and an optional vector(1536). Chunk content
and source provenance remain authoritative in the original tables. Partial batches
are durable but invisible to retrieval until the generation completes. Retrying a
failed/cancelled matching job reuses completed documents and preserves usage.

Input consists of file path, symbol name, normalized signature and original code;
docstrings already present in source are retained. No instructions are extracted
from repository text. The tokenizer partitions long embedding inputs into at most
4096-token parts. Parts are sent as token IDs, avoiding broken Unicode decoding.
A token-weighted mean of normalized part vectors is normalized again to represent
the complete source chunk. This is a documented baseline, not a claim that mean
pooling is optimal. Benchmark alternative chunking before changing it.

The worker processes eight source chunks per checkpoint. Provider calls validate
model, response ordering/count, dimensions, finite/nonzero values, and reported
usage. Redirects and environment proxy inheritance are disabled; the destination
is fixed. No raw provider error bodies, source text or keys are logged.

Before calls, a preflight checks the remaining source against the token budget.
Each batch reserves tokens in a committed, lease-fenced transaction before sending.
Successful batches store documents and confirmed usage together. A crash after a
provider accepts a call can still cause a repeated paid call: distributed delivery
is not exactly once. Reservations remain consumed to bound that uncertainty. The
UI labels reservation-based cost as a conservative estimate, not exact billing.
Explicit retry can increase the job budget only to the new server-configured cap.

## Retrieval and ranking

1. Validate the session, repository ownership, source generation and request bounds.
2. Analyze at most 12 query terms. Retain snake_case identifiers and add split/camel
   components. Bound the query to 512 characters.
3. Lexical channel: PostgreSQL simple-config full-text search with OR terms and
   ts_rank_cd. A GIN expression index supports matching; this is not BM25.
4. Symbol channel: exact lowercased name/qualified-name matches, including nested
   symbols whose definition falls within a chunk and chunks linked to a symbol.
5. Optional vector channel: embed the query with the matching profile and run
   exact cosine nearest-neighbor search filtered to the completed search generation.
6. Take at most 30 candidates per channel. Deduplicate chunk IDs and sum
   1/(60 + rank). Stable path/offset ordering resolves ties.
7. Return the top results and construct a bounded evidence list with path, immutable
   commit, line ranges, chunk ID and source text. Count the serialized JSON, including
   citation metadata, against the context budget. Oversized whole chunks are omitted
   explicitly rather than silently truncating their cited source.

Search API requests use POST and CSRF because semantic queries can spend money and
query text should not appear in URL logs. Database read transactions are released
before the provider wait. The whole search has a 25-second deadline. No provider
failure silently changes hybrid mode into keyword mode; the user can choose free
keyword mode explicitly.

Learned reranking is deliberately postponed until the baseline benchmark exposes
its value. RRF is fusion, not a cross-encoder reranker. Context labels C1/C2 are
retrieval evidence references, not validated citations in a generated answer.
Future generation must treat source as untrusted data and validate every citation.
No model answer or hidden chain-of-thought is produced in this milestone.

## Performance, quality and costs

Exact vector scanning is O(N × 1536) within a bounded generation. A 1536-float vector
uses roughly 6 KiB before row/index overhead; 10000 vectors are about 59 MiB. Measure
latency and filtered recall before adding HNSW or another ANN index. The GIN index
adds write/storage overhead but avoids application-wide text scans. There is no
cross-generation embedding cache yet; retries reuse completed batches only.

Per-user limits: five preparations/minute, three semantic preparation starts/day,
and thirty queries/minute. Defaults are safe for local development because semantic
calls are disabled. For a public paid deployment, per-user limits alone do not
stop multi-account abuse; add registration controls and an enforced global spend
budget. Provider billing/spend settings remain an operational backstop.

The 14-query fixture benchmark is a development regression set, not a held-out
representative code-search benchmark. Compare lexical, symbol, keyword fusion,
vector and hybrid fusion using identical source/candidate budgets. Record Recall@K,
MRR@8, latency, profile/version hashes and usage. Live semantic measurements require
explicit opt-in; passing fake-provider tests is not evidence of semantic quality.
Nearest-neighbor search can return irrelevant results for an unrelated query;
answer abstention/relevance policy and negative-case evaluation come with Q&A.

## References

- https://developers.openai.com/api/docs/guides/embeddings
- https://developers.openai.com/api/reference/resources/embeddings/methods/create
- https://developers.openai.com/api/docs/models/text-embedding-3-small
- https://github.com/pgvector/pgvector
- https://github.com/pgvector/pgvector-python
- https://www.postgresql.org/docs/current/textsearch-indexes.html

Price checked 2026-09-22: standard text-embedding-3-small input price is $0.02 per
million tokens. The application stores a configurable estimate; prices may change.
