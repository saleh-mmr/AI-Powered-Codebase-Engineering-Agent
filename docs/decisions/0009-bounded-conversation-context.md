# ADR 0009: frozen, bounded conversation context

Status: accepted for Milestone 7C1.

Saved messages alone do not give the model memory. Passing the full transcript
would inflate cost, allow stale facts to dominate, and make a queued request change
meaning if another message arrived before execution.

Snapshot up to three recent answered pairs at admission under the existing
conversation row lock. Only the same source-index ID is eligible; stop at the first
ineligible pair. Keep whole newest pairs within 1,000 estimated tokens and 8 KiB.
Store validated JSON on answer_runs. Existing runs default to an empty snapshot.
The snapshot is immutable for idempotent retries and deleted by the existing cascade.
JSON is appropriate for a small immutable value rather than separately editable entities.

The worker revalidates typed history and applies the same bounds. Append the most
recent selected user question as a deterministic retrieval hint; current-question
text gets priority in the 512-character query limit. No additional paid query-rewrite
call is introduced. Build the prompt with history in a separate untrusted data field.
Drop oldest history if needed to preserve the total prompt bound. Record the actual
included turn IDs and token estimate in the saved answer; those fields default for
old snapshots. The prompt/policy fingerprint rejects runs accepted by older builds.

Only current evidence can support citations. No prior evidence/IDs are promoted into
new evidence. Stateless and legacy synchronous endpoints retain empty history.
A summary model and vector conversation memory were rejected for this slice: both
add cost and new quality evaluation requirements before bounded dialogue is verified.

Tradeoffs: latest-user-text hints can dilute a new topic, omission can make pronouns
ambiguous, and history can contain incorrect or adversarial model output. Grounding
requires evaluation beyond citation-ID validation. The fixture adds those cases;
paid scoring and full-stack acceptance remain explicit gates. Prompt history adds
input-token cost but no extra model request. No new library or environment variable.
