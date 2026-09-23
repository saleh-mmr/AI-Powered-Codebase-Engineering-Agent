from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import AnswerRun, Conversation, Repository


class RunStore:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def owned(self, user_id: UUID, run_id: UUID) -> AnswerRun:
        run = await self.db.scalar(
            select(AnswerRun)
            .join(Conversation)
            .join(Repository)
            .where(
                AnswerRun.id == run_id,
                Conversation.user_id == user_id,
                Repository.user_id == user_id,
            )
        )
        if run is None:
            raise AppError("not_found", "Answer run not found.", 404)
        return run

    async def by_key(self, conversation_id: UUID, request_key: UUID) -> AnswerRun | None:
        result: AnswerRun | None = await self.db.scalar(
            select(AnswerRun).where(
                AnswerRun.conversation_id == conversation_id, AnswerRun.request_key == request_key
            )
        )

        return result

    async def recent(self, conversation_id: UUID) -> list[AnswerRun]:
        return list(
            (
                await self.db.scalars(
                    select(AnswerRun)
                    .where(AnswerRun.conversation_id == conversation_id)
                    .order_by(AnswerRun.created_at.desc(), AnswerRun.id.desc())
                    .limit(20)
                )
            ).all()
        )
