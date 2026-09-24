# ADR 0011: stream provisional text with bounded snapshot recovery

Status: accepted for Milestone 7C2B.

The provider previously returned a whole structured answer. Real text deltas improve
feedback but are incomplete JSON and have not passed citation checks. Storing each
token in the lifecycle event table would violate its three-event contract and create
unnecessary rows and replay complexity.

Add an optional StreamingAnswerProvider protocol alongside generate(). Background
AnswerService calls generate_stream() when the adapter supports it; other adapters
retain final-only behavior. OpenAI request construction and final envelope validation
are shared between transports. Preserve the configured model and strict answer schema.
Process only output-text deltas, enforce ordering/identity/budgets, and require a completed
response with matching accumulated text. No repair request or automatic retry is added.

Use Pydantic's existing partial JSON parsing only to project selected strings for display.
Its experimental partial mode is not relied on for answer correctness: the completed
result uses ordinary strict validation. The projection is bounded and tests cover
partial strings, malformed values, control characters and extra non-display fields.
No new dependency is added and no provider-specific objects escape the adapter.

Persist the latest readable snapshot on the run under its lease fence, at most four
writes per second. Clear it on every terminal transition, in the same state/event
transaction. The SSE read protocol gains an opt-in answer.preview frame with run_id,
revision and text, but no event ID. A preview replaces the previous snapshot; it does
not advance Last-Event-ID. Each reconnect sends the current snapshot, and terminal
state sends an empty one. Legacy readers without preview=true retain lifecycle-only frames.

React labels the text provisional, escapes it, and supplies no citation links until
final publication. Polling also hides it when the run becomes terminal. Intermediate
snapshots may be coalesced by one-second SSE polling; these are real received model
deltas, not a typing animation. Fast answers can complete before a preview is observed.
The 8,000-character display limit may truncate a long draft without truncating its final
validated answer. This is a bounded MVP tradeoff, not a zero-latency per-token delivery claim.

Live model quality, proxy timing and cost must be measured locally. The evaluation runner
can select the real streaming transport and record time to first provider text delta;
that number does not measure browser-visible preview latency. Full usage receipts remain 7C3.
