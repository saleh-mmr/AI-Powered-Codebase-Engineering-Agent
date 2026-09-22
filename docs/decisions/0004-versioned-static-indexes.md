# ADR 0004 — Versioned static indexes before retrieval

Status: accepted for Milestone 4.

## Decision

Use the Python standard-library AST parser in the existing Celery worker. A user
explicitly starts indexing an already imported, immutable commit. The API creates
only durable job state; the dispatcher publishes its ID to Redis. No imported
module is imported, evaluated, or executed, and no additional dependency or model
API is required. Python 3.12 is the tested runtime and grammar target.

Use three new tables: repository_indexes, code_symbols, code_chunks. A generation
contains source import ID, immutable commit SHA and parser/chunker version. A
partial unique index permits one current attempt per repository. The newest
completed generation remains readable when a replacement fails or is cancelled.
Requesting the same completed source/pipeline returns it without recomputation.
There is no successful-import refresh yet; do not confuse reindexing stored data
with fetching new commits.

Reuse the small existing claim/lease/dispatch functions with a typed choice of
job model. This is not a generic workflow framework. Workers fence publication
with a conditional update on a live lease, then commit status, symbols, chunks,
and diagnostics together. PostgreSQL row locking serializes starts. At most three
abandoned-worker claims are allowed; explicit parse/storage errors require a user
retry. Cancellation revokes publication rights immediately; CPU work can continue
briefly until its deadline/process limit.

## Source and symbol contracts

Extract classes, functions, methods, imports, module/class variables, lexical
parent scope, decorator-inclusive line ranges, normalized signatures and docstrings.
Function locals, route/model classification and semantic cross-file resolution are
not implemented. Signatures are metadata, not exact source; an overly large/deep
signature is null, while its original source remains intact.

The specification's parent_symbol_id/symbol_id relationships use the equivalent
composite keys (index_id, file_id, ordinal) here. This preserves duplicate names
and overloads. Each symbol/chunk also has a UUID. Database foreign keys enforce
parent/chunk-symbol links and require files and indexes to share an import snapshot.
Repository ownership is reached through the index rather than duplicated on every
row. Foreign resources receive 404 from every read and write endpoint.

## Chunking policy

Keep whole functions/methods when they fit. Nested function symbols remain
inspectable but their source stays within the containing function chunk. A class
with methods contributes header/gap chunks plus method chunks, avoiding duplicate
class-body storage. Empty classes/small classes without methods can be whole chunks.
Retain comments, imports, module code and gaps. There is no overlap in v1.

Chunks are exact non-overlapping source slices. Concatenating chunks in ordinal
order reproduces the complete imported file, including CRLF and final newlines.
Line numbers are one-based and inclusive; offsets are zero-based Python Unicode
character positions with an exclusive end. They are not JavaScript UTF-16 offsets
or Python AST byte columns. Clients render the provided content instead of slicing
with incompatible offsets. A long single line may span several chunks with the
same line number. SHA-256 identifies chunk content; IDs distinguish repeated text.

Each chunk is capped at 8192 UTF-8 bytes. Prefer complete lines; split oversized
lines at character boundaries. This is a storage bound, not a token-count claim.
Milestone 5 will add the embedding provider's tokenizer, token limits and validated
embedding metadata. It will also construct retrieval context with parent signatures
and file paths rather than contaminating exact source slices with synthetic text.

Invalid Python or the node/scope budgets produce a visible diagnostic and text
chunks. Other supported languages receive text chunks, explicitly without Python
symbol claims. File path/language/commit provenance is obtained through joins.
No lexical/vector search, merging, reranking or answer generation is included yet.

## Limits and consequences

The import bounds still apply (256 KiB/file, 10 MiB retained text). Indexing allows
40000 AST nodes/file, 10000 symbols and 10000 chunks/generation, a configurable
90-second deadline and the worker's existing memory/CPU/process controls. A parser
can allocate memory before the node check, so the OS/container boundary matters.
The worker remains a trusted service with application credentials, not a sandbox
for executing repository programs. Separate execution isolation remains mandatory.

Storage is O(source bytes + symbol/chunk metadata) per generation, with an extra
copy of chunk text to support later retrieval. Parsing/chunking is bounded and
in-memory for these MVP-sized imports. Publication is atomic rather than incremental.
No external API cost is incurred. Retention cleanup, incremental indexing, multi-
language parsing, tokenization, and larger repositories are future measured changes.

Reference: Python 3.12 AST documentation, https://docs.python.org/3.12/library/ast.html.
