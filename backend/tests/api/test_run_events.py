import asyncio
import json
from uuid import UUID

import pytest
from sqlalchemy import delete, select
from test_answer_runs import queue, worker
from test_conversations import setup
from test_repositories import sign_in

from app.api.dependencies.auth import SESSION_COOKIE
from app.models import RunEvent, Session
from app.services.run_stream import RunStream

HEADERS = {"X-RepoPilot-Request": "1"}


def event_data(response):
    return [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ") and '"sequence"' in line
    ]


def test_completed_stream_replays_in_order_and_cursor_skips_without_model_calls(auth_client):
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    worker(auth_client, provider, run["id"])
    worker(auth_client, provider, run["id"])
    path = "/answer-runs/" + run["id"] + "/events"
    response = auth_client.get(path, headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["cache-control"] == "no-store"
    events = event_data(response)
    assert [e["status"] for e in events] == ["queued", "running", "completed"]
    assert [e["sequence"] for e in events] == [1, 2, 3]
    assert all(set(e) == {"run_id", "sequence", "status", "occurred_at"} for e in events)
    resumed = auth_client.get(path + "?after=0", headers={**HEADERS, "Last-Event-ID": "2"})
    assert [e["status"] for e in event_data(resumed)] == ["completed"]
    assert event_data(auth_client.get(path + "?after=3", headers=HEADERS)) == []
    assert "stream.end" in response.text
    assert len(provider.calls) == 1


def test_cancelled_and_failed_have_terminal_events(auth_client):
    headers, _, url, provider = setup(auth_client)
    first = queue(auth_client, headers, url).json()
    auth_client.post("/answer-runs/" + first["id"] + "/cancel", json={}, headers=headers)
    events = event_data(auth_client.get("/answer-runs/" + first["id"] + "/events", headers=HEADERS))
    assert [e["status"] for e in events] == ["queued", "cancelled"]
    second = queue(auth_client, headers, url).json()
    provider.fail = True
    worker(auth_client, provider, second["id"])
    events = event_data(
        auth_client.get("/answer-runs/" + second["id"] + "/events", headers=HEADERS)
    )
    assert [e["status"] for e in events] == ["queued", "running", "failed"]


def test_stream_auth_owner_header_cursor_and_bounded_reconnect(auth_client, monkeypatch):
    import app.services.run_stream as streams

    monkeypatch.setattr(streams, "STREAM_POLLS", 2)
    monkeypatch.setattr(streams, "POLL_SECONDS", 0)
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    path = "/answer-runs/" + run["id"] + "/events"
    assert auth_client.get(path).status_code == 403
    assert auth_client.get(path + "?after=3", headers=HEADERS).status_code == 409
    assert auth_client.get(path + "?after=-1", headers=HEADERS).status_code == 422
    assert auth_client.get(path, headers={**HEADERS, "Last-Event-ID": "NaN"}).status_code == 422
    response = auth_client.get(path, headers=HEADERS)
    assert ": keep-alive" in response.text and "stream.reconnect" in response.text
    sign_in(auth_client, "stream-outsider@example.com")
    assert auth_client.get(path, headers=HEADERS).status_code == 404
    auth_client.cookies.clear()
    assert auth_client.get(path, headers=HEADERS).status_code == 401
    assert provider.calls == []


@pytest.mark.parametrize("change", ["logout", "deletion", "disconnect"])
def test_live_stream_rechecks_access_and_stops(auth_client, monkeypatch, change):
    import app.services.run_stream as streams

    monkeypatch.setattr(streams, "POLL_SECONDS", 0)
    headers, _, url, _ = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    state = auth_client.app.state
    raw = auth_client.cookies.get(SESSION_COOKIE)

    async def exercise():
        disconnected = False

        async def is_disconnected():
            return disconnected

        service = RunStream(state.test_factory, state.settings, state.dummy_password_hash)
        frames = service.frames(raw, UUID(run["id"]), 0, is_disconnected)
        first = await anext(frames)
        assert '"queued"' in first
        if change == "logout":
            async with state.test_factory() as db:
                await db.execute(delete(Session))
                await db.commit()
        elif change == "deletion":
            from app.models import Conversation

            async with state.test_factory() as db:
                await db.execute(delete(Conversation))
                await db.commit()
        else:
            disconnected = True
        remaining = [frame async for frame in frames]
        assert not any("event: run.status" in frame for frame in remaining)
        if change == "logout":
            assert any('"unauthenticated"' in frame for frame in remaining)
        elif change == "deletion":
            assert any("stream.error" in frame for frame in remaining)

    asyncio.run(exercise())


def test_completion_event_failure_rolls_back_transcript_and_completion(auth_client, monkeypatch):
    import app.jobs.answer_run as job
    from app.models import AnswerRun

    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    original = job.append_state

    async def fail_completion(db, run_id):
        current = await db.get(AnswerRun, run_id, populate_existing=True)
        if current.status == "completed":
            raise RuntimeError("test event insert failure")
        await original(db, run_id)

    monkeypatch.setattr(job, "append_state", fail_completion)
    worker(auth_client, provider, run["id"])
    assert auth_client.get(url + "/messages").json()["items"] == []
    state = auth_client.get("/answer-runs/" + run["id"]).json()
    assert state["status"] == "failed"
    events = event_data(auth_client.get("/answer-runs/" + run["id"] + "/events", headers=HEADERS))
    assert [e["status"] for e in events] == ["queued", "running", "failed"]
    assert auth_client.delete(url, headers=headers).status_code == 204

    async def count():
        async with auth_client.app.state.test_factory() as db:
            return list((await db.scalars(select(RunEvent))).all())

    assert asyncio.run(count()) == []


def test_stream_connection_rate_limit_is_independent_of_generation(auth_client, monkeypatch):
    import app.services.run_stream as streams
    from app.core.errors import AppError

    monkeypatch.setattr(streams, "STREAM_POLLS", 1)
    monkeypatch.setattr(streams, "POLL_SECONDS", 0)
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()

    class Deny:
        async def check(self, limits):
            assert all(limit.key.startswith("run-stream:") for limit in limits)
            raise AppError("rate_limited", "Wait before reconnecting.", 429)

    auth_client.app.state.rate_limiter = Deny()
    response = auth_client.get("/answer-runs/" + run["id"] + "/events", headers=HEADERS)
    assert response.status_code == 429 and provider.calls == []
