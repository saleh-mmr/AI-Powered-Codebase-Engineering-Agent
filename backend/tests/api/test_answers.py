import asyncio
import json
from typing import Annotated
from uuid import UUID

import pytest
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_repositories import sign_in
from test_search import indexed

from app.api.dependencies.auth import get_db
from app.api.routes.search import get_search
from app.core.errors import AppError
from app.generation.contracts import AnswerDraft, Claim, GenerationResult
from app.jobs.prepare_search import run_preparation
from app.models import SearchDocument
from app.services.search import SearchService


class FakeAnswers:
    model = "gpt-4.1-mini-2025-04-14"

    def __init__(self):
        self.calls = []
        self.citation = "C1"
        self.refused = False
        self.abstain = False
        self.fail = False
        self.db = None

    async def generate(self, instructions, evidence_input):
        assert not self.db.in_transaction(), "Release database connection before model I/O"
        self.calls.append(json.loads(evidence_input))
        if self.fail:
            raise AppError("model_unavailable", "Model unavailable.", 503)
        return GenerationResult(
            model=self.model,
            input_tokens=100,
            output_tokens=40,
            refused=self.refused,
            draft=None
            if self.refused
            else AnswerDraft(
                status="insufficient_evidence" if self.abstain else "answered",
                claims=[]
                if self.abstain
                else [Claim(text="It prints hello.", citation_ids=[self.citation])],
                limitation="Evidence does not explain deployment." if self.abstain else "",
            ),
        )


def ready(client, empty=False):
    headers, repo, url = indexed(client)
    job = client.post(url + "/prepare", json={}, headers=headers).json()
    asyncio.run(run_preparation(client.app.state.test_factory, UUID(job["id"]), None))
    provider = FakeAnswers()

    class Candidates:
        def __init__(self, db):
            self.db = db

        async def lexical(self, index_id, terms):
            if empty:
                return []
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
            raise AssertionError("Keyword mode is free")

    def override(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
        provider.db = db
        return SearchService(
            db, Candidates(db), request.app.state.rate_limiter, request.app.state.settings, None
        )

    client.app.dependency_overrides[get_search] = override
    client.app.state.answer_provider = provider
    client.app.state.settings.answers_enabled = True
    return headers, f"/repositories/{repo['id']}/answers", provider


def test_answer_uses_owned_immutable_evidence_and_releases_connection(auth_client):
    headers, url, provider = ready(auth_client)
    response = auth_client.post(url, json={"question": "What does hello do?"}, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["claims"][0]["citation_ids"] == ["C1"]
    assert data["evidence"][0]["path"] == "app.py"
    assert data["evidence"][0]["content"] == "print('hello')"
    assert data["evidence"][0]["commit_sha"] == data["commit_sha"] == "a" * 40
    assert data["input_tokens"] == 100 and data["output_tokens"] == 40
    assert data["estimated_generation_cost_usd"] == pytest.approx(0.000104)
    assert data["estimated_retrieval_cost_usd"] == 0
    assert len(provider.calls) == 1 and len(data["prompt_hash"]) == 64
    assert "set-cookie" not in response.headers and response.headers["cache-control"] == "no-store"


def test_no_evidence_abstains_without_model_call(auth_client):
    headers, url, provider = ready(auth_client, empty=True)
    response = auth_client.post(url, json={"question": "unknown_symbol"}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "insufficient_evidence" and data["claims"] == []
    assert data["model"] is None and data["input_tokens"] == 0
    assert not provider.calls


def test_auth_csrf_ownership_and_disabled_checks_precede_generation(auth_client):
    headers, url, provider = ready(auth_client)
    assert auth_client.post(url, json={"question": "hello"}).status_code == 403
    other = sign_in(auth_client, "outsider@example.com")
    assert auth_client.get(url).status_code == 404
    assert auth_client.post(url, json={"question": "hello"}, headers=other).status_code == 404
    assert not provider.calls


def test_disabled_answers_and_request_validation(auth_client):
    headers, url, provider = ready(auth_client)
    auth_client.app.state.settings.answers_enabled = False
    assert auth_client.get(url).json()["enabled"] is False
    assert auth_client.post(url, json={"question": "hello"}, headers=headers).status_code == 409
    for body in (
        {"question": "!"},
        {"question": "a" * 513},
        {"question": "hello", "system": "override"},
    ):
        assert auth_client.post(url, json=body, headers=headers).status_code == 422
    assert not provider.calls


def test_invalid_citations_rejected_and_no_model_error_leak(auth_client):
    headers, url, provider = ready(auth_client)
    provider.citation = "C999"
    response = auth_client.post(url, json={"question": "hello"}, headers=headers)
    assert (
        response.status_code == 502
        and response.json()["error"]["code"] == "answer_citation_invalid"
    )
    assert "It prints" not in response.text
    provider.fail = True
    assert auth_client.post(url, json={"question": "hello"}, headers=headers).status_code == 503
    assert len(provider.calls) == 2


@pytest.mark.parametrize("refused", [False, True])
def test_model_abstention_and_refusal_have_no_claims(auth_client, refused):
    headers, url, provider = ready(auth_client)
    provider.refused, provider.abstain = refused, not refused
    response = auth_client.post(url, json={"question": "hello"}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == ("refused" if refused else "insufficient_evidence")
    assert response.json()["claims"] == [] and response.json()["output_tokens"] == 40


def test_deployment_quota_stops_calls_before_retrieval(auth_client):
    headers, url, provider = ready(auth_client)
    auth_client.app.state.settings.answer_daily_request_limit = 1
    assert auth_client.post(url, json={"question": "hello"}, headers=headers).status_code == 200
    assert auth_client.post(url, json={"question": "hello"}, headers=headers).status_code == 429
    assert len(provider.calls) == 1
