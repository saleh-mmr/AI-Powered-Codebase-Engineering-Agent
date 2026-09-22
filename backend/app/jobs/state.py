from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from app.indexing.errors import LeaseLost
from app.models import ImportJob, Repository, RepositoryIndex, SearchIndex


@dataclass(frozen=True)
class Claim:
    job_id: UUID
    repository_id: UUID
    lease_token: UUID
    owner: str
    name: str
    attempt: int


async def claim_job(
    factory: async_sessionmaker[AsyncSession],
    job_id: UUID,
    model: type[ImportJob] | type[RepositoryIndex] | type[SearchIndex] = ImportJob,
) -> Claim | None:
    now = datetime.now(UTC)
    lease = uuid4()
    async with factory() as db:
        job = (
            await db.execute(
                update(model)
                .where(
                    model.id == job_id,
                    model.is_current.is_(True),
                    model.attempts < 3,
                    model.available_at <= now,
                    or_(
                        model.status == "queued",
                        and_(model.status == "running", model.lease_expires_at < now),
                    ),
                )
                .values(
                    status="running",
                    stage="starting",
                    attempts=model.attempts + 1,
                    lease_token=lease,
                    lease_expires_at=now + timedelta(seconds=180),
                    started_at=now,
                    finished_at=None,
                    error_code=None,
                    error_message=None,
                )
                .returning(model.id, model.repository_id, model.attempts)
            )
        ).one_or_none()
        if job is None:
            return None
        repository = await db.get(Repository, job.repository_id)
        if repository is None:
            return None
        result = Claim(
            job.id, repository.id, lease, repository.owner, repository.name, job.attempts
        )
        await db.commit()
        return result


def lease_condition(
    claim: Claim, model: type[ImportJob] | type[RepositoryIndex] | type[SearchIndex] = ImportJob
) -> ColumnElement[bool]:
    return and_(
        model.id == claim.job_id,
        model.status == "running",
        model.lease_token == claim.lease_token,
        model.is_current.is_(True),
        model.lease_expires_at > datetime.now(UTC),
    )


async def report_stage(
    factory: async_sessionmaker[AsyncSession],
    claim: Claim,
    stage: str,
    model: type[ImportJob] | type[RepositoryIndex] | type[SearchIndex] = ImportJob,
) -> None:
    async with factory() as db:
        found = await db.scalar(
            update(model)
            .where(lease_condition(claim, model))
            .values(stage=stage)
            .returning(model.id)
        )
        if found is None:
            raise LeaseLost()
        await db.commit()
