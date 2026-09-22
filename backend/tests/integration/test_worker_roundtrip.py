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

    async def cleanup():
        engine = create_engine(settings)
        try:
            async with engine.begin() as connection:
                await connection.execute(delete(User).where(User.id == user_id))
        finally:
            await engine.dispose()

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
    finally:
        asyncio.run(cleanup())
