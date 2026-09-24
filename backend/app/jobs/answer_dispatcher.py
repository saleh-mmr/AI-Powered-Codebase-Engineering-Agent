import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AnswerRun
from app.repositories.run_event import append_state

logger = logging.getLogger("repopilot.answer_dispatcher")


async def dispatch_answers(
    factory: async_sessionmaker[AsyncSession], publish: Callable[[UUID], Awaitable[None]]
) -> None:
    now = datetime.now(UTC)
    async with factory() as db:
        # Never reclaim running paid work: a crashed worker may already have spent money.
        expired = list(
            (
                await db.scalars(
                    update(AnswerRun)
                    .where(AnswerRun.status == "running", AnswerRun.lease_expires_at < now)
                    .values(
                        status="failed",
                        finished_at=now,
                        lease_token=None,
                        lease_expires_at=None,
                        error_code="answer_worker_lost",
                        error_message=(
                            "Worker stopped; usage is unknown. No automatic retry was made."
                        ),
                    )
                    .returning(AnswerRun.id)
                )
            ).all()
        )
        for run_id in expired:
            await append_state(db, run_id)
        expired = list(
            (
                await db.scalars(
                    update(AnswerRun)
                    .where(
                        AnswerRun.status == "queued",
                        AnswerRun.created_at <= now - timedelta(hours=1),
                    )
                    .values(
                        status="failed",
                        finished_at=now,
                        error_code="answer_queue_expired",
                        error_message="Run waited over an hour. Check worker availability.",
                    )
                    .returning(AnswerRun.id)
                )
            ).all()
        )
        for run_id in expired:
            await append_state(db, run_id)
        ids = list(
            (
                await db.scalars(
                    select(AnswerRun.id)
                    .where(
                        AnswerRun.status == "queued",
                        or_(
                            AnswerRun.last_dispatched_at.is_(None),
                            AnswerRun.last_dispatched_at < now - timedelta(seconds=30),
                        ),
                    )
                    .order_by(AnswerRun.created_at)
                    .limit(50)
                )
            ).all()
        )
        await db.commit()
    for run_id in ids:
        try:
            await publish(run_id)
        except Exception as exc:
            logger.warning(
                "answer_publish_failed",
                extra={"job_id": str(run_id), "error_type": type(exc).__name__},
            )
            continue
        async with factory() as db:
            await db.execute(
                update(AnswerRun)
                .where(AnswerRun.id == run_id, AnswerRun.status == "queued")
                .values(last_dispatched_at=now)
            )
            await db.commit()
