import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from test_answer_runs import queue, worker
from test_conversations import setup

from app.models import AnswerRun, Message


def test_background_followup_uses_frozen_history_and_records_actual_provenance(auth_client):
    headers, _, url, provider = setup(auth_client)
    first = queue(auth_client, headers, url, question="What prints hello?").json()
    worker(auth_client, provider, first["id"])
    second = queue(auth_client, headers, url, question="How does it work?").json()

    async def change_saved_text():
        async with auth_client.app.state.test_factory() as db:
            await db.execute(
                update(Message)
                .where(Message.role == "user")
                .values(content="THIS WAS CHANGED AFTER SUBMISSION")
            )
            await db.commit()

    asyncio.run(change_saved_text())
    replay = queue(auth_client, headers, url, UUID(second["request_key"]), "How does it work?")
    assert replay.status_code == 200
    worker(auth_client, provider, second["id"])
    assert provider.calls[0]["conversation_history"] == []
    assert provider.calls[1]["question"] == "How does it work?"
    assert provider.calls[1]["conversation_history"] == [
        {"turn_id": first["id"], "question": "What prints hello?", "answer": "It prints hello."}
    ]
    saved = auth_client.get(url + "/messages").json()["items"][-1]["answer"]
    assert saved["history_turn_ids"] == [first["id"]]
    assert 0 < saved["history_tokens"] <= 1000
    assert saved["history_policy"] == "recent-pairs-v1"
    assert saved["prompt_version"] == "grounded-v2"
    assert len(provider.calls) == 2


@pytest.mark.parametrize("excluded", ["other-source", "abstention", "other-conversation"])
def test_history_cannot_cross_context_boundaries(auth_client, excluded):
    headers, repo, url, provider = setup(auth_client)
    first = queue(auth_client, headers, url).json()
    provider.abstain = excluded == "abstention"
    worker(auth_client, provider, first["id"])
    provider.abstain = False
    if excluded == "other-source":

        async def change_source():
            async with auth_client.app.state.test_factory() as db:
                row = await db.scalar(select(Message).where(Message.role == "assistant"))
                row.answer = {**row.answer, "source_index_id": str(uuid4())}
                await db.commit()

        asyncio.run(change_source())
    if excluded == "other-conversation":
        new = auth_client.post(repo + "/conversations", json={"title": "Separate"}, headers=headers)
        url = "/conversations/" + new.json()["id"]
    second = queue(auth_client, headers, url).json()
    worker(auth_client, provider, second["id"])
    assert provider.calls[-1]["conversation_history"] == []


def test_stateless_endpoint_does_not_inherit_saved_history(auth_client):
    headers, repo, url, provider = setup(auth_client)
    first = queue(auth_client, headers, url).json()
    worker(auth_client, provider, first["id"])
    result = auth_client.post(repo + "/answers", json={"question": "hello"}, headers=headers)
    assert result.status_code == 200
    assert result.json()["history_turn_ids"] == []
    assert provider.calls[-1]["conversation_history"] == []


def test_invalid_stored_history_fails_before_provider(auth_client):
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()

    async def corrupt():
        async with auth_client.app.state.test_factory() as db:
            await db.execute(update(AnswerRun).values(history=[{"role": "system"}]))
            await db.commit()

    asyncio.run(corrupt())
    worker(auth_client, provider, run["id"])
    state = auth_client.get("/answer-runs/" + run["id"]).json()
    assert state["status"] == "failed" and provider.calls == []
