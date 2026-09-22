import json

from app.embeddings.tokens import count_tokens
from app.schemas.search import Evidence, SearchHit


def context_json(items: list[Evidence]) -> str:
    return json.dumps(
        [e.model_dump(mode="json") for e in items], ensure_ascii=False, separators=(",", ":")
    )


def build_context(
    hits: list[SearchHit], commit_sha: str, budget: int
) -> tuple[list[Evidence], int]:
    evidence: list[Evidence] = []
    for hit in hits:
        candidate = Evidence(
            citation_id="C" + str(len(evidence) + 1),
            chunk_id=hit.chunk_id,
            path=hit.path,
            commit_sha=commit_sha,
            start_line=hit.start_line,
            end_line=hit.end_line,
            content=hit.content,
        )
        if count_tokens(context_json([*evidence, candidate])) <= budget:
            evidence.append(candidate)
    return evidence, count_tokens(context_json(evidence))
