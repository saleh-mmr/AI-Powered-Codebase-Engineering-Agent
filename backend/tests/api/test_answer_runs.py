import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from test_conversations import setup
from test_repositories import sign_in

from app.jobs.answer_dispatcher import dispatch_answers
from app.jobs.answer_run import run_answer
from app.models import AnswerRun, SearchDocument
from app.services.answers import AnswerService
from app.services.search import SearchService


def queue(client, headers, url, key=None, question="hello"):
    return client.post(
        url + "/runs",
        json={"question": question, "mode": "keyword", "request_key": str(key or uuid4())},
        headers=headers,
    )


def worker(client, provider, run_id):
    class Candidates:
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
            raise AssertionError("No vector call in keyword mode")

    def build(db):
        provider.db = db
        state = client.app.state
        search = SearchService(db, Candidates(db), state.rate_limiter, state.settings, None)
        return AnswerService(db, search, state.rate_limiter, state.settings, provider)

    asyncio.run(
        run_answer(client.app.state.test_factory, UUID(run_id), client.app.state.settings, build)
    )


def test_submission_replay_conflict_and_single_active(auth_client):
    headers, _, url, provider = setup(auth_client)
    key = uuid4()
    first = queue(auth_client, headers, url, key)
    assert first.status_code == 202, first.text
    assert first.json()["status"] == "queued" and first.json()["usage_state"] == "not_started"
    duplicate = queue(auth_client, headers, url, key)
    assert duplicate.status_code == 200 and duplicate.json()["id"] == first.json()["id"]
    assert queue(auth_client, headers, url, key, "different").status_code == 409
    assert queue(auth_client, headers, url).status_code == 409
    assert provider.calls == []
    assert auth_client.get(url + "/messages").json()["items"] == []


def test_worker_publishes_once_with_usage_and_replay_after_completion(auth_client):
    headers, _, url, provider = setup(auth_client)
    key = uuid4()
    response = queue(auth_client, headers, url, key).json()
    run_id = response["id"]
    worker(auth_client, provider, run_id)
    worker(auth_client, provider, run_id)
    run = auth_client.get("/answer-runs/" + run_id).json()
    assert run["status"] == "completed" and run["usage_state"] == "recorded"
    assert run["input_tokens"] == 100 and run["output_tokens"] == 40
    assert run["estimated_cost_usd"] == pytest.approx(0.000104)
    messages = auth_client.get(url + "/messages").json()["items"]
    assert len(messages) == 2 and messages[1]["turn_id"] == run_id
    assert messages[1]["answer"]["answer_id"] == run_id
    assert len(provider.calls) == 1
    assert queue(auth_client, headers, url, key).json()["status"] == "completed"
    assert len(provider.calls) == 1


def test_cancel_queued_prevents_provider_call(auth_client):
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    path = "/answer-runs/" + run["id"]
    assert (
        auth_client.post(path + "/cancel", json={}, headers=headers).json()["status"] == "cancelled"
    )
    worker(auth_client, provider, run["id"])
    assert provider.calls == []
    assert auth_client.get(path).json()["usage_state"] == "not_started"
    assert auth_client.post(path + "/cancel", json={}, headers=headers).status_code == 409


def test_running_cancellation_fences_transcript_publication(auth_client):
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    generate = provider.generate

    async def cancel_then_generate(instructions, evidence_input):
        result = await generate(instructions, evidence_input)
        async with auth_client.app.state.test_factory() as db:
            await db.execute(
                update(AnswerRun)
                .where(AnswerRun.id == UUID(run["id"]))
                .values(
                    status="cancelled",
                    lease_token=None,
                    lease_expires_at=None,
                    finished_at=datetime.now(UTC),
                )
            )
            await db.commit()
        return result

    provider.generate = cancel_then_generate
    worker(auth_client, provider, run["id"])
    state = auth_client.get("/answer-runs/" + run["id"]).json()
    assert state["status"] == "cancelled" and state["usage_state"] == "unknown"
    assert auth_client.get(url + "/messages").json()["items"] == []


@pytest.mark.parametrize("failure", ["provider", "citation", "config"])
def test_failures_are_terminal_not_automatically_retried(auth_client, failure):
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    if failure == "provider":
        provider.fail = True
    elif failure == "citation":
        provider.citation = "C999"
    else:
        auth_client.app.state.settings.answer_max_output_tokens = 1500
    worker(auth_client, provider, run["id"])
    worker(auth_client, provider, run["id"])
    result = auth_client.get("/answer-runs/" + run["id"]).json()
    assert result["status"] == "failed" and result["usage_state"] == "unknown"
    assert result["estimated_cost_usd"] is None
    assert len(provider.calls) == (0 if failure == "config" else 1)
    assert auth_client.get(url + "/messages").json()["items"] == []


def test_dispatch_retry_and_expired_worker_never_regenerate(auth_client):
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    factory = auth_client.app.state.test_factory
    published = []

    async def failed_publish(key):
        raise ConnectionError("test broker unavailable")

    async def publish(key):
        published.append(str(key))

    asyncio.run(dispatch_answers(factory, failed_publish))
    asyncio.run(dispatch_answers(factory, publish))
    asyncio.run(dispatch_answers(factory, publish))
    assert published == [run["id"]]

    async def expire():
        async with factory() as db:
            await db.execute(
                update(AnswerRun).values(
                    status="running",
                    usage_state="unknown",
                    lease_token=uuid4(),
                    lease_expires_at=datetime.now(UTC) - timedelta(seconds=1),
                )
            )
            await db.commit()

    asyncio.run(expire())
    asyncio.run(dispatch_answers(factory, publish))
    result = auth_client.get("/answer-runs/" + run["id"]).json()
    assert result["status"] == "failed" and result["error_code"] == "answer_worker_lost"
    worker(auth_client, provider, run["id"])
    assert provider.calls == [] and published == [run["id"]]


def test_owner_checks_and_csrf_cover_run_routes(auth_client):
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    path = "/answer-runs/" + run["id"]
    assert auth_client.post(path + "/cancel", json={}).status_code == 403
    other = sign_in(auth_client, "run-outsider@example.com")
    assert auth_client.get(path).status_code == 404
    assert auth_client.get(url + "/runs").status_code == 404
    assert queue(auth_client, other, url).status_code == 404
    assert auth_client.post(path + "/cancel", json={}, headers=other).status_code == 404
    assert provider.calls == []


def test_deleted_conversation_and_expired_queue_make_no_calls(auth_client):
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    factory = auth_client.app.state.test_factory

    async def expire():
        async with factory() as db:
            await db.execute(
                update(AnswerRun).values(created_at=datetime.now(UTC) - timedelta(hours=2))
            )
            await db.commit()

    async def publish(key):
        raise AssertionError("Expired queue must not be published")

    asyncio.run(expire())
    asyncio.run(dispatch_answers(factory, publish))
    assert (
        auth_client.get("/answer-runs/" + run["id"]).json()["error_code"] == "answer_queue_expired"
    )
    worker(auth_client, provider, run["id"])
    assert auth_client.delete(url, headers=headers).status_code == 204
    worker(auth_client, provider, run["id"])
    assert auth_client.get("/answer-runs/" + run["id"]).status_code == 404
    assert provider.calls == []


def test_source_change_rejected_before_generation(auth_client):
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()

    async def change_pin():
        async with auth_client.app.state.test_factory() as db:
            await db.execute(update(AnswerRun).values(source_index_id=uuid4()))
            await db.commit()

    asyncio.run(change_pin())
    worker(auth_client, provider, run["id"])
    state = auth_client.get("/answer-runs/" + run["id"]).json()
    assert state["error_code"] == "answer_source_changed" and provider.calls == []
