# ADR 0012 — Usage outlives answer publication

Status: accepted for Milestone 7C3.

An answer can fail citation checks or be cancelled after a billable call. Keeping usage
only in the transaction that publishes messages loses that evidence. Logs alone are
not a durable accounting interface.

Use one receipt per run and purpose (generation/query_embedding). Commit an unknown
attempt before starting a call, then record independently validated usage in a separate
short transaction. A receipt failure before dispatch prevents the call. Database or
worker failure after a response can leave an unknown receipt; no retry is automatic.
Cancellation fences publication, not accounting. Receipt completion never updates run
status or creates messages. Parent deletion cascades and late completion never recreates
records. This is application telemetry, not an invoice ledger or exactly-once billing.

The unique (run_id, kind) index supports listing and enforces the current one-call-per-
purpose workflow. Future retries need explicit attempt numbering and a new migration.
Numeric rates are captured per million tokens at call start; Numeric cost avoids binary
floating-point accumulation. Rates are configuration, not authoritative vendor prices.
Cached-token discounts, provider credits, taxes and other billing adjustments are absent.

The adapter can carry validated usage in a safe ProviderUsageError when structured
output fails. Missing, inconsistent or untrusted usage remains unknown. Receipts contain
no prompts, repository text, API keys, raw errors or model reasoning.

A receipt_version marker distinguishes old runs from newly tracked runs. Existing run
aggregate fields retain their API semantics for compatibility; the new owner-authorized
usage endpoint is the detailed source. The known subtotal excludes unknown attempts
and must not be described as a final bill. The UI retrieves receipts on demand.

Scope: background answer runs only. Standalone search/answer endpoints and indexing
continue their existing usage behavior. Billing reconciliation is deferred.
