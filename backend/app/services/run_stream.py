"""Short-lived, replayable streams. No DB connection is held while waiting/sending."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.models import RunEvent
from app.repositories.answer_run import RunStore
from app.repositories.run_event import after
from app.schemas.run_event import RunEventResponse
from app.services.auth import AuthService

logger = logging.getLogger("repopilot.run_stream")
TERMINAL = {"completed", "failed", "cancelled"}
STREAM_POLLS = 25
POLL_SECONDS = 1.0


@dataclass(frozen=True)
class EventPage:
    user_id: UUID
    events: list[RunEventResponse]
    terminal: bool


class RunStream:
    def __init__(
        self, factory: async_sessionmaker[AsyncSession], settings: Settings, dummy_hash: str
    ):
        self.factory, self.settings, self.dummy_hash = factory, settings, dummy_hash

    async def page(self, raw_token: str | None, run_id: UUID, cursor: int) -> EventPage:
        async with self.factory() as db:
            identity = await AuthService(
                db, self.settings.session_lifetime_hours, self.dummy_hash
            ).authenticate(raw_token)
            run = await RunStore(db).owned(identity.user.id, run_id)
            maximum = await db.scalar(
                select(func.max(RunEvent.sequence)).where(RunEvent.run_id == run_id)
            )
            if cursor > (maximum or 0):
                raise AppError(
                    "event_cursor_invalid",
                    "Event cursor is ahead of this run. Reload its timeline.",
                    409,
                )
            events = await after(db, run_id, cursor)
            return EventPage(identity.user.id, events, run.status in TERMINAL)

    async def frames(
        self,
        raw_token: str | None,
        run_id: UUID,
        cursor: int,
        disconnected: Callable[[], Awaitable[bool]],
    ) -> AsyncIterator[str]:
        started = perf_counter()
        try:
            for tick in range(STREAM_POLLS):
                if await disconnected():
                    return
                # Reauthenticate/reauthorize every poll, including before the first frame.
                page = await self.page(raw_token, run_id, cursor)
                for event in page.events:
                    cursor = event.sequence
                    yield f"id: {cursor}\nevent: run.status\ndata: {event.model_dump_json()}\n\n"
                if page.terminal:
                    yield "event: stream.end\ndata: {}\n\n"
                    return
                if tick % 5 == 0:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(POLL_SECONDS)
            yield "event: stream.reconnect\ndata: {}\n\n"
        except AppError as exc:
            # HTTP headers may already be sent. A safe control frame closes the stream.
            code = "unauthenticated" if exc.status == 401 else "stream_unavailable"
            yield f'event: stream.error\ndata: {{"code":"{code}"}}\n\n'
        except Exception as exc:
            logger.warning(
                "run_stream_failed", extra={"job_id": str(run_id), "error_type": type(exc).__name__}
            )
            yield 'event: stream.error\ndata: {"code":"stream_unavailable"}\n\n'
        finally:
            logger.info(
                "run_stream_closed",
                extra={
                    "job_id": str(run_id),
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
