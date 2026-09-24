from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnswerRun, RunEvent
from app.schemas.run_event import RunEventResponse


async def append_state(db: AsyncSession, run_id: UUID) -> None:
    """Caller holds the run's write lock, and commits event + transition together."""
    run = await db.get(AnswerRun, run_id, populate_existing=True)
    if run is None:
        return
    if run.status in {"completed", "failed", "cancelled"}:
        run.preview_text = ""
    sequence = await db.scalar(select(func.max(RunEvent.sequence)).where(RunEvent.run_id == run_id))
    db.add(RunEvent(run_id=run_id, sequence=(sequence or 0) + 1, status=run.status))
    await db.flush()


async def after(db: AsyncSession, run_id: UUID, cursor: int) -> list[RunEventResponse]:
    rows = await db.scalars(
        select(RunEvent)
        .where(RunEvent.run_id == run_id, RunEvent.sequence > cursor)
        .order_by(RunEvent.sequence)
        .limit(3)
    )
    return [RunEventResponse.model_validate(row) for row in rows]
