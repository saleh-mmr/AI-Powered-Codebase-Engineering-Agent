from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from app.indexing.errors import LeaseLost
from app.models import ImportJob, Repository


@dataclass(frozen=True)
class Claim:
    job_id: UUID
    repository_id: UUID
    lease_token: UUID
    owner: str
    name: str
    attempt: int


async def claim_job(factory: async_sessionmaker[AsyncSession], job_id: UUID) -> Claim | None:
    now = datetime.now(UTC)
    lease = uuid4()
    async with factory() as db:
        job = (
            await db.scalars(
                update(ImportJob)
                .where(
                    ImportJob.id == job_id,
                    ImportJob.is_current.is_(True),
                    ImportJob.attempts < 3,
                    ImportJob.available_at <= now,
                    or_(
                        ImportJob.status == "queued",
                        and_(ImportJob.status == "running", ImportJob.lease_expires_at < now),
                    ),
                )
                .values(
                    status="running",
                    stage="metadata",
                    attempts=ImportJob.attempts + 1,
                    lease_token=lease,
                    lease_expires_at=now + timedelta(seconds=180),
                    started_at=now,
                    finished_at=None,
                    error_code=None,
                    error_message=None,
                )
                .returning(ImportJob)
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


def lease_condition(claim: Claim) -> ColumnElement[bool]:
    return and_(
        ImportJob.id == claim.job_id,
        ImportJob.status == "running",
        ImportJob.lease_token == claim.lease_token,
        ImportJob.is_current.is_(True),
        ImportJob.lease_expires_at > datetime.now(UTC),
    )


async def report_stage(factory: async_sessionmaker[AsyncSession], claim: Claim, stage: str) -> None:
    async with factory() as db:
        found = await db.scalar(
            update(ImportJob)
            .where(lease_condition(claim))
            .values(stage=stage)
            .returning(ImportJob.id)
        )
        if found is None:
            raise LeaseLost()
        await db.commit()
