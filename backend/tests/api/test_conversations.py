import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from test_answers import ready
from test_repositories import sign_in

from app.models import Conversation, Message, RepositoryIndex, User
from app.repositories.conversation import ConversationStore
from app.schemas.answer import AnswerResponse


def setup(client):
    headers, answer_url, provider = ready(client)
    repository_url = answer_url.removesuffix("/answers")
    created = client.post(
        repository_url + "/conversations", json={"title": "  Code questions  "}, headers=headers
    )
    assert created.status_code == 201, created.text
    assert created.json()["title"] == "Code questions"
    url = "/conversations/" + created.json()["id"]
    return headers, repository_url, url, provider


def test_saved_answer_pair_survives_reload_and_index_deletion(auth_client):
    headers, repo, url, provider = setup(auth_client)
    response = auth_client.post(
        url + "/messages", json={"question": "What prints hello?"}, headers=headers
    )
    assert response.status_code == 201, response.text
    page = auth_client.get(url + "/messages").json()
    assert page["next_before"] is None
    question, answer = page["items"]
    assert [question["role"], answer["role"]] == ["user", "assistant"]
    assert [question["position"], answer["position"]] == [1, 2]
    assert question["turn_id"] == answer["turn_id"] == response.json()["answer_id"]
    assert question["token_count"] is None and answer["token_count"] == 40
    assert answer["answer"] == response.json()
    assert auth_client.get(url).json()["message_count"] == 2
    assert auth_client.get(repo + "/conversations").json()["items"][0]["message_count"] == 2

    async def remove_index():
        async with auth_client.app.state.test_factory() as db:
            await db.execute(delete(RepositoryIndex))
            await db.commit()

    asyncio.run(remove_index())
    assert (
        auth_client.get(url + "/messages").json()["items"][1]["answer"]["evidence"][0]["content"]
        == "print('hello')"
    )
    assert len(provider.calls) == 1  # Loading history never generates again.


def test_ownership_and_csrf_before_generation(auth_client):
    headers, repo, url, provider = setup(auth_client)
    assert auth_client.post(url + "/messages", json={"question": "hello"}).status_code == 403
    assert auth_client.delete(url).status_code == 403
    other = sign_in(auth_client, "outsider2@example.com")
    for path in (repo + "/conversations", url, url + "/messages"):
        assert auth_client.get(path).status_code == 404
    assert (
        auth_client.post(url + "/messages", json={"question": "hello"}, headers=other).status_code
        == 404
    )
    assert auth_client.delete(url, headers=other).status_code == 404
    assert (
        auth_client.post(
            repo + "/conversations", json={"title": "foreign"}, headers=other
        ).status_code
        == 404
    )
    assert provider.calls == []


@pytest.mark.parametrize("failure", ["provider", "citation"])
def test_failed_answers_leave_no_partial_transcript(auth_client, failure):
    headers, _, url, provider = setup(auth_client)
    provider.fail = failure == "provider"
    if failure == "citation":
        provider.citation = "C999"
    response = auth_client.post(url + "/messages", json={"question": "hello"}, headers=headers)
    assert response.status_code in {502, 503}
    assert auth_client.get(url).json()["message_count"] == 0
    assert auth_client.get(url + "/messages").json()["items"] == []


def test_pagination_and_atomic_pair_rollback(auth_client):
    headers, _, url, _ = setup(auth_client)
    response = auth_client.post(url + "/messages", json={"question": "hello"}, headers=headers)
    answer = AnswerResponse.model_validate(response.json())
    conversation_id = UUID(url.rsplit("/", 1)[1])
    factory = auth_client.app.state.test_factory

    async def seed():
        async with factory() as db:
            conversation = await db.get(Conversation, conversation_id)
            for i in range(12):
                copy = answer.model_copy(update={"answer_id": uuid4()})
                await ConversationStore(db).append_pair(
                    conversation.user_id, conversation_id, f"question {i}", copy
                )
            await db.commit()
            # Duplicate turn violates unique constraint. Counter and inserts roll back together.
            with pytest.raises(IntegrityError):
                await ConversationStore(db).append_pair(
                    conversation.user_id, conversation_id, "duplicate", answer
                )
            await db.rollback()

    asyncio.run(seed())
    first = auth_client.get(url + "/messages").json()
    assert len(first["items"]) == 20 and first["next_before"] == 7
    assert [m["position"] for m in first["items"]] == list(range(7, 27))
    older = auth_client.get(url + "/messages?before=7").json()
    assert [m["position"] for m in older["items"]] == list(range(1, 7))
    assert older["next_before"] is None
    assert auth_client.get(url).json()["message_count"] == 26
    assert auth_client.get(url + "/messages?before=0").status_code == 422


def test_owner_constraint_and_delete_cascade(auth_client):
    headers, repo, url, _ = setup(auth_client)
    assert (
        auth_client.post(url + "/messages", json={"question": "hello"}, headers=headers).status_code
        == 201
    )
    conversation_id = UUID(url.rsplit("/", 1)[1])
    factory = auth_client.app.state.test_factory

    async def mismatch():
        async with factory() as db:
            other = User(email="constraint@example.com", name="Other", password_hash="unused")
            db.add(other)
            await db.flush()
            with pytest.raises(IntegrityError):
                await db.execute(
                    update(Conversation)
                    .where(Conversation.id == conversation_id)
                    .values(user_id=other.id)
                )
            await db.rollback()

    asyncio.run(mismatch())
    assert auth_client.delete(url, headers=headers).status_code == 204
    assert auth_client.get(url).status_code == 404

    async def count():
        async with factory() as db:
            return await db.scalar(select(func.count()).select_from(Message))

    assert asyncio.run(count()) == 0
    new = auth_client.post(
        repo + "/conversations", json={"title": "second"}, headers=headers
    ).json()
    assert auth_client.delete(repo, headers=headers).status_code == 204
    assert auth_client.get("/conversations/" + new["id"]).status_code == 404


def test_full_conversation_and_invalid_title_are_rejected(auth_client):
    headers, repo, url, provider = setup(auth_client)
    for title in (" ", "x" * 101, "bad\nname"):
        assert (
            auth_client.post(
                repo + "/conversations", json={"title": title}, headers=headers
            ).status_code
            == 422
        )

    async def fill():
        async with auth_client.app.state.test_factory() as db:
            await db.execute(update(Conversation).values(message_count=200))
            await db.commit()

    asyncio.run(fill())
    assert (
        auth_client.post(url + "/messages", json={"question": "hello"}, headers=headers).status_code
        == 409
    )
    assert provider.calls == []


def test_conversation_deleted_during_generation_is_not_recreated(auth_client):
    headers, _, url, provider = setup(auth_client)
    generate = provider.generate

    async def remove_then_generate(instructions, evidence_input):
        async with auth_client.app.state.test_factory() as db:
            await db.execute(delete(Conversation))
            await db.commit()
        return await generate(instructions, evidence_input)

    provider.generate = remove_then_generate
    assert (
        auth_client.post(url + "/messages", json={"question": "hello"}, headers=headers).status_code
        == 404
    )
    assert auth_client.get(url).status_code == 404
