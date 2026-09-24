from datetime import UTC, datetime
from time import monotonic
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError
from app.generation.preview import preview_text
from app.models import AnswerRun

PREVIEW_INTERVAL = 0.25


class PreviewWriter:
    def __init__(self, factory: async_sessionmaker[AsyncSession], run_id: UUID, token: UUID):
        self.factory, self.run_id, self.token = factory, run_id, token
        self.raw = ""
        self.previous = ""
        self.written_at = float("-inf")

    async def delta(self, value: str) -> None:
        self.raw += value
        if len(self.raw.encode()) > 64 * 1024:
            raise AppError("model_invalid", "Model output exceeds the stream limit.", 502)
        now = monotonic()
        if now - self.written_at < PREVIEW_INTERVAL:
            return
        text = preview_text(self.raw)
        if text == self.previous:
            return
        async with self.factory() as db:
            updated = await db.scalar(
                update(AnswerRun)
                .where(
                    AnswerRun.id == self.run_id,
                    AnswerRun.status == "running",
                    AnswerRun.lease_token == self.token,
                    AnswerRun.lease_expires_at > datetime.now(UTC),
                    AnswerRun.preview_revision < 256,
                )
                .values(preview_text=text, preview_revision=AnswerRun.preview_revision + 1)
                .returning(AnswerRun.id)
            )
            if updated is None:
                raise AppError(
                    "answer_stopped", "The answer run no longer accepts streamed output.", 409
                )
            await db.commit()
        self.previous, self.written_at = text, now
