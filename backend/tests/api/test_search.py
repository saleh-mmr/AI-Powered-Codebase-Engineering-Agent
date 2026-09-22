import asyncio
from typing import Annotated
from uuid import UUID

import pytest
from fastapi import Depends, Request
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from test_indexes import imported
from test_repositories import sign_in

from app.api.dependencies.auth import get_db
from app.api.routes.search import get_search
from app.core.errors import AppError
from app.embeddings.provider import DIMENSIONS, PROFILE, EmbeddingBatch
from app.indexing.errors import LeaseLost
from app.jobs.index_repository import run_index
from app.jobs.prepare_search import checkpoint, run_preparation
from app.jobs.state import claim_job
from app.models import RepositoryFile, SearchDocument, SearchIndex
from app.services.search import SearchService


class FakeProvider:
    profile = PROFILE

    def __init__(self, fail_on: int = 0):
        self.calls = 0
        self.fail_on = fail_on

    def tokenize(self, text):
        from app.embeddings.tokens import token_parts

        return token_parts(text)

    async def embed(self, inputs):
        self.calls += 1
        if self.calls == self.fail_on:
            raise AppError("embedding_unavailable", "Provider unavailable.", 503)
        return EmbeddingBatch(
            [[1.0] + [0.0] * (DIMENSIONS - 1) for _ in inputs], sum(map(len, inputs))
        )


def indexed(client: TestClient, content: str | None = None):
    headers, repo, index_url = imported(client)
    factory = client.app.state.test_factory
    if content:

        async def replace():
            async with factory() as db:
                await db.execute(update(RepositoryFile).values(content=content))
                await db.commit()

        asyncio.run(replace())
    job = client.post(index_url, json={}, headers=headers).json()
    asyncio.run(run_index(factory, UUID(job["id"])))
    return headers, repo, f"/repositories/{repo['id']}/search"


def test_keyword_preparation_idempotence_and_ownership(auth_client: TestClient) -> None:
    headers, repo, url = indexed(auth_client)
    assert auth_client.get(url).json()["keyword"] is None
    assert (
        auth_client.post(url + "/prepare", json={"mode": "hybrid"}, headers=headers).status_code
        == 409
    )
    queued = auth_client.post(url + "/prepare", json={}, headers=headers)
    assert queued.status_code == 202
    assert auth_client.post(url + "/prepare", json={}, headers=headers).status_code == 409
    asyncio.run(
        run_preparation(auth_client.app.state.test_factory, UUID(queued.json()["id"]), None)
    )
    state = auth_client.get(url).json()
    assert state["keyword"]["documents_stored"] == 1
    assert state["keyword"]["reserved_tokens"] == 0
    assert auth_client.post(url + "/prepare", json={}, headers=headers).status_code == 200
    assert auth_client.post(url + "/query", json={"query": "hello"}).status_code == 403
    other = sign_in(auth_client, "another@example.com")
    assert auth_client.get(url).status_code == 404
    assert (
        auth_client.post(url + "/query", json={"query": "hello"}, headers=other).status_code == 404
    )
    assert auth_client.post(url + "/prepare", json={}, headers=other).status_code == 404
    assert auth_client.post(url + "/cancel", json={}, headers=other).status_code == 404


def test_failed_embedding_job_resumes_and_keeps_usage(auth_client: TestClient) -> None:
    content = "".join(f"def f{i}():\n    return {i}\n" for i in range(10))
    headers, _, url = indexed(auth_client, content)
    auth_client.app.state.settings.embeddings_enabled = True
    provider = FakeProvider(fail_on=2)
    first = auth_client.post(url + "/prepare", json={"mode": "hybrid"}, headers=headers).json()
    factory = auth_client.app.state.test_factory
    asyncio.run(run_preparation(factory, UUID(first["id"]), provider))
    state = auth_client.get(url).json()
    assert state["hybrid"] is None
    assert state["latest"]["status"] == "failed" and state["latest"]["documents_stored"] == 8
    reserved = state["latest"]["reserved_tokens"]
    retry = auth_client.post(url + "/prepare", json={"mode": "hybrid"}, headers=headers).json()
    assert retry["id"] == first["id"]
    asyncio.run(run_preparation(factory, UUID(retry["id"]), provider))
    state = auth_client.get(url).json()
    assert state["hybrid"]["documents_stored"] == 10 and provider.calls == 3
    assert state["hybrid"]["reserved_tokens"] > reserved
    assert state["hybrid"]["input_tokens"] < state["hybrid"]["reserved_tokens"]


def test_budget_preflight_makes_no_provider_calls(auth_client: TestClient) -> None:
    headers, _, url = indexed(auth_client, "def f():\n    return '" + "alpha " * 2000 + "'\n")
    auth_client.app.state.settings.embeddings_enabled = True
    auth_client.app.state.settings.embedding_token_budget = 1000
    job = auth_client.post(url + "/prepare", json={"mode": "hybrid"}, headers=headers).json()
    provider = FakeProvider()
    asyncio.run(run_preparation(auth_client.app.state.test_factory, UUID(job["id"]), provider))
    assert provider.calls == 0
    assert auth_client.get(url).json()["latest"]["error_code"] == "embedding_budget_exceeded"


def test_cancel_fences_publication(auth_client: TestClient) -> None:
    headers, _, url = indexed(auth_client)
    job = auth_client.post(url + "/prepare", json={}, headers=headers).json()
    factory = auth_client.app.state.test_factory
    claim = asyncio.run(claim_job(factory, UUID(job["id"]), SearchIndex))
    assert claim is not None
    assert auth_client.post(url + "/cancel", json={}, headers=headers).status_code == 204
    with pytest.raises(LeaseLost):
        asyncio.run(checkpoint(factory, claim, [], 0))


def test_search_api_uses_pinned_source_and_bounded_context(auth_client: TestClient) -> None:
    headers, _, url = indexed(auth_client)
    job = auth_client.post(url + "/prepare", json={}, headers=headers).json()
    factory = auth_client.app.state.test_factory
    asyncio.run(run_preparation(factory, UUID(job["id"]), None))

    class StubCandidates:
        def __init__(self, db):
            self.db = db

        async def lexical(self, index_id, terms):
            return list(
                (
                    await self.db.scalars(
                        select(SearchDocument.chunk_id).where(
                            SearchDocument.search_index_id == index_id
                        )
                    )
                ).all()
            )

        async def symbols(self, index_id, terms):
            return []

        async def vector(self, index_id, vector):
            raise AssertionError("Free search must not call vector search")

    def override(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
        return SearchService(
            db, StubCandidates(db), request.app.state.rate_limiter, request.app.state.settings, None
        )

    auth_client.app.dependency_overrides[get_search] = override
    response = auth_client.post(
        url + "/query", json={"query": "hello", "context_token_budget": 100}, headers=headers
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["results"][0]["content"] == "print('hello')"
    assert data["results"][0]["channel_ranks"] == {"lexical": 1}
    assert data["commit_sha"] == "a" * 40 and data["query_tokens"] == 0
    assert data["context_tokens"] <= 100
    assert auth_client.post(url + "/query", json={"query": "!"}, headers=headers).status_code == 422
    assert (
        auth_client.post(
            url + "/query", json={"query": "hi", "top_k": 100}, headers=headers
        ).status_code
        == 422
    )


def test_search_cascade_deletes_vectors(auth_client: TestClient) -> None:
    headers, repo, url = indexed(auth_client)
    job = auth_client.post(url + "/prepare", json={}, headers=headers).json()
    factory = auth_client.app.state.test_factory
    asyncio.run(run_preparation(factory, UUID(job["id"]), None))
    assert auth_client.delete(f"/repositories/{repo['id']}", headers=headers).status_code == 204

    async def verify():
        async with factory() as db:
            assert await db.scalar(select(func.count()).select_from(SearchDocument)) == 0

    asyncio.run(verify())


def test_hybrid_query_checks_profile_and_ownership_before_provider_calls(
    auth_client: TestClient,
) -> None:
    headers, _, url = indexed(auth_client)
    auth_client.app.state.settings.embeddings_enabled = True
    provider = FakeProvider()
    job = auth_client.post(url + "/prepare", json={"mode": "hybrid"}, headers=headers).json()
    factory = auth_client.app.state.test_factory
    asyncio.run(run_preparation(factory, UUID(job["id"]), provider))
    provider.calls = 0

    class Candidates:
        def __init__(self, db):
            self.db = db

        async def lexical(self, index_id, terms):
            return []

        async def symbols(self, index_id, terms):
            return []

        async def vector(self, index_id, vector):
            assert len(vector) == DIMENSIONS
            return list(
                (
                    await self.db.scalars(
                        select(SearchDocument.chunk_id).where(
                            SearchDocument.search_index_id == index_id
                        )
                    )
                ).all()
            )

    def override(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
        return SearchService(
            db, Candidates(db), request.app.state.rate_limiter, request.app.state.settings, provider
        )

    auth_client.app.dependency_overrides[get_search] = override
    response = auth_client.post(
        url + "/query", json={"query": "hello", "mode": "hybrid"}, headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["channel_ranks"] == {"vector": 1}
    assert response.json()["query_tokens"] > 0
    assert response.json()["estimated_query_cost_usd"] > 0
    assert provider.calls == 1

    async def change_profile():
        async with factory() as db:
            await db.execute(update(SearchIndex).values(provider_profile="different-space"))
            await db.commit()

    asyncio.run(change_profile())
    assert (
        auth_client.post(
            url + "/query", json={"query": "hello", "mode": "hybrid"}, headers=headers
        ).status_code
        == 409
    )
    assert provider.calls == 1
    other = sign_in(auth_client, "unrelated@example.com")
    assert (
        auth_client.post(
            url + "/query", json={"query": "hello", "mode": "hybrid"}, headers=other
        ).status_code
        == 404
    )
    assert provider.calls == 1
