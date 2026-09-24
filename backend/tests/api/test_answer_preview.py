import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from test_answer_runs import queue, worker
from test_conversations import setup

from app.api.dependencies.auth import SESSION_COOKIE
from app.core.errors import AppError
from app.jobs.answer_preview import PreviewWriter
from app.models import AnswerRun, Conversation
from app.services.answer_runs import RunService
from app.services.run_stream import RunStream


@pytest.mark.parametrize("outcome", ["completed", "citation", "provider", "cancelled"])
def test_preview_is_visible_only_while_running_and_never_saved_as_an_answer(
    auth_client, monkeypatch, outcome
):
    import app.jobs.answer_preview as previews

    monkeypatch.setattr(previews, "PREVIEW_INTERVAL", 0)
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    state = auth_client.app.state
    raw = auth_client.cookies.get(SESSION_COOKIE)
    observed = []
    generate = provider.generate

    async def stream(instructions, evidence_input, on_delta):
        # This callback runs during generation, before any validated final response exists.
        await on_delta('{"claims":[{"text":"Unvalidated draft')
        service = RunStream(state.test_factory, state.settings, state.dummy_password_hash)
        page = await service.page(raw, UUID(run["id"]), 0)
        observed.append(page.preview.text)
        assert page.terminal is False
        if outcome == "cancelled":
            async with state.test_factory() as db:
                conversation = await db.get(Conversation, UUID(run["conversation_id"]))
                await RunService(db, state.rate_limiter, state.settings).cancel(
                    conversation.user_id, UUID(run["id"])
                )
            await on_delta(" more")  # The cancellation fence rejects subsequent writes.
            raise AssertionError("Cancelled sink should reject")
        if outcome == "provider":
            raise AppError("model_incomplete", "Stream interrupted.", 502)
        if outcome == "citation":
            provider.citation = "C999"
        return await generate(instructions, evidence_input)

    provider.generate_stream = stream
    worker(auth_client, provider, run["id"])
    assert observed == ["Unvalidated draft"]
    result = auth_client.get("/answer-runs/" + run["id"]).json()
    assert result["status"] == ("failed" if outcome in {"citation", "provider"} else outcome)

    async def inspect():
        async with state.test_factory() as db:
            stored = await db.get(AnswerRun, UUID(run["id"]))
            assert stored.preview_text == "" and stored.preview_revision == 1

    asyncio.run(inspect())
    messages = auth_client.get(url + "/messages").json()["items"]
    assert len(messages) == (2 if outcome == "completed" else 0)
    assert "Unvalidated draft" not in str(messages)
    response = auth_client.get(
        "/answer-runs/" + run["id"] + "/events?preview=true", headers={"X-RepoPilot-Request": "1"}
    )
    assert "event: answer.preview" in response.text and '"text":""' in response.text
    assert "Unvalidated draft" not in response.text


def test_reconnect_returns_latest_snapshot_without_advancing_lifecycle_cursor(
    auth_client, monkeypatch
):
    import app.services.run_stream as streams

    monkeypatch.setattr(streams, "STREAM_POLLS", 1)
    monkeypatch.setattr(streams, "POLL_SECONDS", 0)
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    token = uuid4()

    async def write():
        async with auth_client.app.state.test_factory() as db:
            await db.execute(
                update(AnswerRun).values(
                    status="running",
                    lease_token=token,
                    lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
                )
            )
            await db.commit()
        sink = PreviewWriter(auth_client.app.state.test_factory, UUID(run["id"]), token)
        await sink.delta('{"claims":[{"text":"Latest partial answer')

    asyncio.run(write())
    path = "/answer-runs/" + run["id"] + "/events"
    headers = {"X-RepoPilot-Request": "1", "Last-Event-ID": "1"}
    assert "answer.preview" not in auth_client.get(path, headers=headers).text
    for _ in range(2):
        response = auth_client.get(path + "?preview=true", headers=headers)
        assert "Latest partial answer" in response.text and "id:" not in response.text
    assert provider.calls == []


def test_preview_sink_enforces_lease_and_throttles_writes(auth_client, monkeypatch):
    import app.jobs.answer_preview as previews

    clock = [100.0]
    monkeypatch.setattr(previews, "monotonic", lambda: clock[0])
    headers, _, url, _ = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    token = uuid4()
    factory = auth_client.app.state.test_factory

    async def exercise():
        async with factory() as db:
            await db.execute(
                update(AnswerRun).values(
                    status="running",
                    lease_token=token,
                    lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
                )
            )
            await db.commit()
        sink = PreviewWriter(factory, UUID(run["id"]), token)
        await sink.delta('{"claims":[{"text":"A')
        await sink.delta("B")
        async with factory() as db:
            row = await db.scalar(select(AnswerRun))
            assert row.preview_text == "A" and row.preview_revision == 1
            await db.execute(
                update(AnswerRun).values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await db.commit()
        clock[0] += 1
        with pytest.raises(AppError, match="no longer accepts"):
            await sink.delta("C")

    asyncio.run(exercise())
