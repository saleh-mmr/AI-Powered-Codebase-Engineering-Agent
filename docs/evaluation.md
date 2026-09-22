# Retrieval evaluation methodology

## Dataset and purpose

backend/evaluation/retrieval/v1/ contains seven synthetic Python source files and
14 manually authored questions with relevant path::qualified_symbol labels. Cases
cover exact identifiers, lexical questions, paraphrases and multiple relevant
functions. Distractors include similarly worded notification/display code. Source
is parsed, never imported or executed.

This is a development regression fixture, not a held-out benchmark or a claim of
production RAG accuracy. Before tuning retrieval on real repositories, add licensed,
commit-pinned examples and separate development/held-out sets. Include no-answer,
ambiguous, multilingual and cross-file cases. Keep labels reviewed by a human.

Offline validation here confirmed all labels resolve: 26 source chunks and 1236
embedding-input tokens with the locked tokenizer. These are corpus measurements,
not retrieval-quality scores or provider billing results.

## Runner and fairness

The CLI uses the actual source-index worker, search-preparation worker, PostgreSQL
candidate queries, RRF and context constructor. It requires a dedicated database
ending in _test and removes its own fixture account afterward. Relevance labels are
validated against extracted symbols before metrics are reported.

All channel ablations use the same prepared corpus and candidates. Keyword mode
reports lexical, symbol and lexical+symbol fusion; hybrid adds vector and full fusion.
It embeds each query once, not once per ablation. Up to 30 candidates/channel feed
an eight-result ranking. Stable path/source offsets break ties. There is no learned
reranking. Do not compare only the handful of example queries in the browser.

## Metrics

Recall@K = distinct relevant labels returned in the first K results / all relevant
labels for the question. Duplicate chunks for one symbol do not increase recall.
MRR@8 = mean reciprocal rank of the first relevant result within eight results;
missing relevant results contribute zero. Reports include per-case rankings so
aggregate improvements cannot hide regressions on important questions.

Report p50/p95 latency using the measured main retrieval request per case; p95 uses
the nearest-rank definition. This small sequential corpus is not a load benchmark.
Reports capture dataset/corpus hashes, pipeline/provider profile, tokenizer version,
preparation usage/reservations and query usage/cost. Provider aliases can change
behavior over time; matching configuration alone does not guarantee bitwise replay.

The CI sanity gate is keyword Recall@5 >= 0.5 on this fixture. It is a modest
regression floor, not a hiring/production quality threshold. Raise it only after
reviewing baseline results, failure cases and intended behavior. Semantic quality
has no asserted threshold until a live run is reviewed. Fake-provider tests verify
shape/ordering/budget/security behavior, not semantic relevance.

## Commands

Follow docs/milestone-5.md to configure isolated PostgreSQL and migrate it. From
repopilot-ai/backend:

```bash
uv run python -m app.evaluation.retrieval --mode keyword --output evaluation/retrieval/reports/keyword.json
```

For a consciously authorized real-provider run, with APP_EMBEDDINGS_ENABLED=true
and your API key configured:

```bash
uv run python -m app.evaluation.retrieval --mode hybrid --allow-paid --output evaluation/retrieval/reports/hybrid.json
```

Generated reports are ignored by Git by default. Review and deliberately commit
selected baselines alongside their configuration when establishing regression
thresholds. CI uploads its keyword report; no provider secrets are supplied to CI.

## What is not measured yet

No answer exists, so groundedness, answer correctness and generated citation
correctness are not claimed. Context provenance/budgets have behavior tests. No
agent exists, so task completion/test pass rate/iteration cost are later metrics.
Relevant-neighbor retrieval alone does not prove that sufficient evidence exists
to answer a question. Add explicit abstention evaluation when Q&A is introduced.
