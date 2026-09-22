import asyncio
import math
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import AppError
from app.embeddings.openai import OpenAIEmbeddings
from app.embeddings.provider import DIMENSIONS, aggregate
from app.embeddings.tokens import count_tokens, encoding, token_parts
from app.evaluation.metrics import recall_at_k, reciprocal_rank
from app.retrieval.context import build_context, context_json
from app.retrieval.ranking import fuse
from app.retrieval.text import query_terms
from app.schemas.search import SearchHit, SearchRequest


def test_token_parts_preserve_all_input_and_handle_special_strings() -> None:
    text = "α🧠<|endoftext|>" * 1000
    parts = token_parts(text)
    assert max(map(len, parts)) <= 4096
    assert encoding().decode([token for part in parts for token in part]) == text
    assert sum(map(len, parts)) == count_tokens(text)


def test_rrf_deduplicates_per_channel_and_has_stable_ties() -> None:
    a, b = UUID(int=1), UUID(int=2)
    ranked = fuse({"lexical": [a, a, b], "vector": [b, a]})
    assert [r.chunk_id for r in ranked] == [a, b]
    assert ranked[0].score == pytest.approx(1 / 61 + 1 / 62)
    assert ranked[0].channel_ranks == {"lexical": 1, "vector": 2}
    assert fuse({"a": [a], "b": [b]}, tie_keys={a: "z", b: "a"})[0].chunk_id == b


def test_identifier_analysis_and_validation() -> None:
    assert "verify_token" in query_terms("Where is verify_token?")
    assert {"verify", "token"} <= set(query_terms("verifyToken"))
    with pytest.raises(ValidationError):
        SearchRequest(query="!!!")
    with pytest.raises(ValidationError):
        SearchRequest(query="token", top_k=100)
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql+asyncpg://u:p@localhost/db", embeddings_enabled=True)


def test_context_budget_counts_serialized_metadata_and_preserves_source() -> None:
    hit = SearchHit(
        chunk_id=uuid4(),
        file_id=uuid4(),
        path="auth.py",
        language="python",
        symbol="f",
        start_line=1,
        end_line=1,
        start_offset=0,
        end_offset=1000,
        content="secret " * 1000,
        score=0.1,
        channel_ranks={"lexical": 1},
    )
    items, tokens = build_context([hit], "a" * 40, 100)
    assert items == [] and tokens == count_tokens("[]")
    items, tokens = build_context([hit], "a" * 40, 6000)
    assert tokens == count_tokens(context_json(items)) <= 6000
    assert items[0].content == hit.content and items[0].citation_id == "C1"


def test_retrieval_metrics_count_distinct_relevant_items() -> None:
    assert recall_at_k(["a", "a", "b"], {"a", "b"}, 2) == 0.5
    assert reciprocal_rank(["x", "a", "b"], {"a", "b"}) == 0.5
    assert reciprocal_rank([], {"a"}) == 0
    with pytest.raises(ValueError):
        recall_at_k([], set(), 3)


def payload():
    return {
        "model": "text-embedding-3-small",
        "data": [{"index": 0, "embedding": [1.0] + [0.0] * (DIMENSIONS - 1)}],
        "usage": {"prompt_tokens": 2},
    }


@pytest.mark.parametrize("mutation", ["dimensions", "nan", "zero", "index", "usage", "model"])
def test_rejects_malformed_provider_vectors_without_leaking_payload(mutation: str) -> None:
    data = payload()
    if mutation == "dimensions":
        data["data"][0]["embedding"] = [1.0]
    if mutation == "nan":
        data["data"][0]["embedding"][0] = float("nan")
    if mutation == "zero":
        data["data"][0]["embedding"] = [0.0] * DIMENSIONS
    if mutation == "index":
        data["data"][0]["index"] = 4
    if mutation == "usage":
        data["usage"]["prompt_tokens"] = 3
    if mutation == "model":
        data["model"] = "other"

    async def run():
        import json

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, content=json.dumps(data)))
        ) as client:
            with pytest.raises(AppError) as error:
                await OpenAIEmbeddings(client, "never-log-this-key").embed([[1, 2]])
            assert error.value.code == "embedding_invalid"
            assert "never-log" not in str(error.value)

    asyncio.run(run())


@pytest.mark.parametrize("status", [401, 429, 500, 302])
def test_provider_http_failures_are_explicit(status: int) -> None:
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(status, text="sensitive provider body")
            )
        ) as client:
            with pytest.raises(AppError) as error:
                await OpenAIEmbeddings(client, "key").embed([[1, 2]])
            assert "sensitive" not in str(error.value)

    asyncio.run(run())


def test_provider_reorders_and_normalizes_vectors_and_aggregate() -> None:
    data = payload()
    data["data"] = [
        {"index": 1, "embedding": [0.0, 2.0] + [0.0] * (DIMENSIONS - 2)},
        data["data"][0],
    ]
    data["usage"]["prompt_tokens"] = 4

    async def run():
        def handler(request):
            assert request.url.host == "api.openai.com"
            assert request.headers["Authorization"] == "Bearer key"
            return httpx.Response(200, json=data)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            response = await OpenAIEmbeddings(client, "key").embed([[1, 2], [3, 4]])
            assert response.vectors[0][0] == 1 and response.vectors[1][1] == 1
            combined = aggregate(response.vectors, [1, 1])
            assert combined[:2] == pytest.approx([1 / math.sqrt(2)] * 2)

    asyncio.run(run())
