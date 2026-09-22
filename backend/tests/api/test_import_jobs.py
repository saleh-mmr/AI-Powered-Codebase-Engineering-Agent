import asyncio
import io
import tarfile
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from test_repositories import connect, sign_in

from app.indexing.archive import read_archive
from app.indexing.errors import ImportFailure, LeaseLost
from app.integrations.github.client import RepositorySource
from app.jobs.dispatcher import dispatch_once
from app.jobs.import_repository import publish_result, run_import
from app.jobs.state import claim_job, report_stage
from app.models import ImportJob, RepositoryFile


class FakeGitHub:
    fail = False
    calls = 0

    async def resolve(self, owner: str, name: str):
        self.calls += 1
        if self.fail:
            raise ImportFailure("github_network_error", "Temporary issue", True)
        return RepositorySource(42, owner, name, "main", "a" * 40)

    async def download(self, source):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:gz") as tar:
            for path, content in [("r/app.py", b"print('hello')"), ("r/.env", b"SECRET=x")]:
                info = tarfile.TarInfo(path)
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
        return data.getvalue()


def test_import_is_atomic_idempotent_and_browsable(auth_client: TestClient) -> None:
    headers = sign_in(auth_client)
    item = connect(auth_client, headers).json()
    factory = auth_client.app.state.test_factory
    fake = FakeGitHub()

    async def run():
        await run_import(factory, fake, UUID(item["job"]["id"]), 10)
        await run_import(factory, fake, UUID(item["job"]["id"]), 10)
        async with factory() as db:
            assert await db.scalar(select(func.count()).select_from(RepositoryFile)) == 1

    asyncio.run(run())
    assert fake.calls == 1
    repo = auth_client.get(f"/repositories/{item['id']}").json()
    assert repo["job"]["status"] == "completed"
    assert repo["job"]["files_skipped"] == 1
    files = auth_client.get(f"/repositories/{item['id']}/files").json()["items"]
    content = auth_client.get(f"/repositories/{item['id']}/files/{files[0]['id']}")
    assert content.json()["content"] == "print('hello')"
    assert content.json()["commit_sha"] == "a" * 40
    assert (
        auth_client.post(f"/repositories/{item['id']}/retry", json={}, headers=headers).status_code
        == 409
    )


def test_cancelled_worker_cannot_publish(auth_client: TestClient) -> None:
    headers = sign_in(auth_client)
    item = connect(auth_client, headers).json()
    factory = auth_client.app.state.test_factory
    claim = asyncio.run(claim_job(factory, UUID(item["job"]["id"])))
    assert claim is not None
    assert (
        auth_client.post(f"/repositories/{item['id']}/cancel", json={}, headers=headers).status_code
        == 204
    )

    async def publish():
        import pytest

        fake = FakeGitHub()
        source = await fake.resolve("owner", "repo")
        with pytest.raises(LeaseLost):
            await publish_result(factory, claim, source, read_archive(await fake.download(source)))
        async with factory() as db:
            assert await db.scalar(select(func.count()).select_from(RepositoryFile)) == 0

    asyncio.run(publish())


def test_expired_lease_takeover_fences_previous_worker(auth_client: TestClient) -> None:
    headers = sign_in(auth_client)
    item = connect(auth_client, headers).json()
    factory = auth_client.app.state.test_factory

    async def scenario():
        import pytest

        job_id = UUID(item["job"]["id"])
        first = await claim_job(factory, job_id)
        assert first is not None
        assert await claim_job(factory, job_id) is None
        async with factory() as db:
            await db.execute(
                update(ImportJob)
                .where(ImportJob.id == job_id)
                .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await db.commit()
        second = await claim_job(factory, job_id)
        assert second is not None and second.attempt == 2
        with pytest.raises(LeaseLost):
            await report_stage(factory, first, "storing")
        await report_stage(factory, second, "downloading")

    asyncio.run(scenario())


def test_dispatch_failure_preserves_job_and_can_retry(auth_client: TestClient) -> None:
    headers = sign_in(auth_client)
    item = connect(auth_client, headers).json()
    factory = auth_client.app.state.test_factory
    published = []

    async def failure(job_id):
        raise ConnectionError("queue down")

    async def success(job_id):
        published.append(job_id)

    async def scenario():
        await dispatch_once(factory, failure)
        await dispatch_once(factory, success)
        await dispatch_once(factory, success)

    asyncio.run(scenario())
    assert published == [UUID(item["job"]["id"])]
    assert auth_client.get(f"/repositories/{item['id']}").json()["job"]["status"] == "queued"


def test_transient_failure_is_bounded(auth_client: TestClient) -> None:
    headers = sign_in(auth_client)
    item = connect(auth_client, headers).json()
    factory = auth_client.app.state.test_factory
    fake = FakeGitHub()
    fake.fail = True

    async def scenario():
        for _ in range(3):
            await run_import(factory, fake, UUID(item["job"]["id"]), 10)
            async with factory() as db:
                await db.execute(
                    update(ImportJob).values(available_at=datetime.now(UTC) - timedelta(seconds=1))
                )
                await db.commit()

    asyncio.run(scenario())
    result = auth_client.get(f"/repositories/{item['id']}").json()
    assert result["job"]["status"] == "failed" and result["job"]["attempts"] == 3
