import asyncio
import io
import os
import tarfile
from uuid import uuid4

import pytest
from celery.contrib.testing.worker import start_worker
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.database.session import create_engine
from app.indexing.pipeline import PIPELINE_VERSION
from app.integrations.github.client import GitHubClient, RepositorySource
from app.models import CodeChunk, ImportJob, Repository, RepositoryFile, RepositoryIndex, User


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_QUEUE_TESTS") != "1",
    reason="requires isolated PostgreSQL/Redis test infrastructure",
)
def test_celery_import_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.jobs.celery_app import celery_app

    settings = Settings()
    assert settings.database_url.get_secret_value().split("?")[0].endswith("_test"), (
        "Use a dedicated database ending in _test"
    )
    user_id, repo_id, job_id = uuid4(), uuid4(), uuid4()
    index_id = uuid4()
    search_id = uuid4()
    conversation_id, answer_id = uuid4(), uuid4()
    queue = "test-" + uuid4().hex

    async def resolve(self, owner, name):
        return RepositorySource(42, owner, name, "main", "a" * 40)

    async def download(self, source):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            data = b'print("worker fixture")'
            info = tarfile.TarInfo("root/main.py")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        return buffer.getvalue()

    monkeypatch.setattr(GitHubClient, "resolve", resolve)
    monkeypatch.setattr(GitHubClient, "download", download)

    async def setup():
        engine = create_engine(settings)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as db:
                db.add(
                    User(
                        id=user_id,
                        email=f"{user_id}@example.com",
                        name="Worker fixture",
                        password_hash="not-used-by-this-test",
                    )
                )
                await db.flush()
                db.add(
                    Repository(
                        id=repo_id,
                        user_id=user_id,
                        source_key="fixture/repo",
                        owner="fixture",
                        name="repo",
                    )
                )
                await db.flush()
                db.add(ImportJob(id=job_id, repository_id=repo_id))
                await db.commit()
        finally:
            await engine.dispose()

    async def verify():
        engine = create_engine(settings)
        try:
            for _ in range(100):
                async with async_sessionmaker(engine)() as db:
                    state = await db.scalar(select(ImportJob.status).where(ImportJob.id == job_id))
                    if state == "completed":
                        file = await db.scalar(
                            select(RepositoryFile).where(RepositoryFile.import_job_id == job_id)
                        )
                        assert file.content == 'print("worker fixture")'
                        return
                    assert state != "failed"
                await asyncio.sleep(0.1)
            raise AssertionError("Worker did not complete within 10 seconds")
        finally:
            await engine.dispose()

    async def queue_index():
        engine = create_engine(settings)
        try:
            async with async_sessionmaker(engine)() as db:
                db.add(
                    RepositoryIndex(
                        id=index_id,
                        repository_id=repo_id,
                        import_job_id=job_id,
                        commit_sha="a" * 40,
                        pipeline_version=PIPELINE_VERSION,
                    )
                )
                await db.commit()
        finally:
            await engine.dispose()

    async def verify_index():
        engine = create_engine(settings)
        try:
            for _ in range(100):
                async with async_sessionmaker(engine)() as db:
                    state = await db.scalar(
                        select(RepositoryIndex.status).where(RepositoryIndex.id == index_id)
                    )
                    if state == "completed":
                        chunk = await db.scalar(
                            select(CodeChunk).where(CodeChunk.index_id == index_id)
                        )
                        assert chunk.content == 'print("worker fixture")'
                        return
                    assert state != "failed"
                await asyncio.sleep(0.1)
            raise AssertionError("Index worker did not complete within 10 seconds")
        finally:
            await engine.dispose()

    async def queue_search():
        from app.models import SearchIndex
        from app.retrieval.text import VERSION

        engine = create_engine(settings)
        try:
            async with async_sessionmaker(engine)() as db:
                db.add(
                    SearchIndex(
                        id=search_id,
                        repository_id=repo_id,
                        source_index_id=index_id,
                        commit_sha="a" * 40,
                        pipeline_version=VERSION,
                        mode="keyword",
                        provider_profile="none",
                        token_budget=200000,
                        price_per_million=0,
                    )
                )
                await db.commit()
        finally:
            await engine.dispose()

    async def verify_search():
        from app.models import SearchIndex

        engine = create_engine(settings)
        try:
            for _ in range(100):
                async with async_sessionmaker(engine)() as db:
                    state = await db.scalar(
                        select(SearchIndex.status).where(SearchIndex.id == search_id)
                    )
                    if state == "completed":
                        return
                    assert state != "failed"
                await asyncio.sleep(0.1)
            raise AssertionError("Search worker did not complete within 10 seconds")
        finally:
            await engine.dispose()

    async def queue_answer():
        from app.jobs.answer_config import config_hash
        from app.models import AnswerRun, Conversation

        engine = create_engine(settings)
        try:
            async with async_sessionmaker(engine)() as db:
                db.add(
                    Conversation(
                        id=conversation_id,
                        user_id=user_id,
                        repository_id=repo_id,
                        title="Worker answers",
                    )
                )
                await db.flush()
                db.add(
                    AnswerRun(
                        id=answer_id,
                        conversation_id=conversation_id,
                        request_key=uuid4(),
                        request_hash="a" * 64,
                        question="worker fixture",
                        mode="keyword",
                        source_index_id=index_id,
                        config_hash=config_hash(settings),
                        model=settings.answer_model,
                    )
                )
                await db.commit()
        finally:
            await engine.dispose()

    async def verify_answer():
        from app.models import AnswerRun, Message

        engine = create_engine(settings)
        try:
            for _ in range(100):
                async with async_sessionmaker(engine)() as db:
                    run = await db.get(AnswerRun, answer_id)
                    if run.status == "completed":
                        messages = list(
                            (
                                await db.scalars(
                                    select(Message).where(Message.turn_id == answer_id)
                                )
                            ).all()
                        )
                        assert len(messages) == 2 and run.usage_state == "recorded"
                        assert run.input_tokens == 100 and run.output_tokens == 20
                        return
                    assert run.status != "failed", run.error_code
                await asyncio.sleep(0.1)
            raise AssertionError("Answer worker did not complete within 10 seconds")
        finally:
            await engine.dispose()

    async def cleanup():
        engine = create_engine(settings)
        try:
            async with engine.begin() as connection:
                await connection.execute(delete(User).where(User.id == user_id))
        finally:
            await engine.dispose()

    from app.generation import factory as generation_factory
    from app.generation.contracts import AnswerDraft, Claim, GenerationResult
    from app.jobs import celery_app as worker_module

    class FakeAnswers:
        model = settings.answer_model

        async def generate(self, instructions, evidence_input):
            return GenerationResult(
                model=self.model,
                refused=False,
                input_tokens=100,
                output_tokens=20,
                draft=AnswerDraft(
                    status="answered",
                    claims=[Claim(text="Prints worker fixture.", citation_ids=["C1"])],
                    limitation="",
                ),
            )

    monkeypatch.setattr(
        generation_factory, "create_answer_provider", lambda config, client: FakeAnswers()
    )
    monkeypatch.setattr(worker_module.settings, "answers_enabled", True)

    asyncio.run(setup())
    try:
        with start_worker(
            celery_app, pool="solo", queues=[queue], perform_ping_check=False, loglevel="ERROR"
        ):
            celery_app.send_task("repopilot.import_repository", args=[str(job_id)], queue=queue)
            asyncio.run(verify())
            asyncio.run(queue_index())
            celery_app.send_task("repopilot.index_repository", args=[str(index_id)], queue=queue)
            asyncio.run(verify_index())
            asyncio.run(queue_search())
            celery_app.send_task("repopilot.prepare_search", args=[str(search_id)], queue=queue)
            asyncio.run(verify_search())
            asyncio.run(queue_answer())
            celery_app.send_task("repopilot.answer_run", args=[str(answer_id)], queue=queue)
            celery_app.send_task("repopilot.answer_run", args=[str(answer_id)], queue=queue)
            asyncio.run(verify_answer())
    finally:
        asyncio.run(cleanup())
