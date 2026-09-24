from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies.auth import SESSION_COOKIE
from app.core.errors import AppError
from app.core.rate_limits import Limit, RateLimiter
from app.schemas.health import ErrorResponse
from app.services.run_stream import RunStream

router = APIRouter(tags=["answer runs"])


@router.get(
    "/answer-runs/{run_id}/events",
    response_class=StreamingResponse,
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 429, 503)},
)
async def events(
    run_id: UUID,
    request: Request,
    after: Annotated[int, Query(ge=0, le=3)] = 0,
    last_event_id: Annotated[str | None, Header(max_length=10)] = None,
) -> StreamingResponse:
    # Custom header requires CORS preflight cross-origin; the app enables no CORS.
    if request.headers.get("x-repopilot-request") != "1":
        raise AppError("csrf_failed", "Use the application to open this stream.", 403)
    cursor = after
    if last_event_id is not None:
        if last_event_id not in {"0", "1", "2", "3"}:
            raise AppError("event_cursor_invalid", "Invalid event cursor.", 422)
        cursor = int(last_event_id)  # Last-Event-ID takes precedence over ?after.
    state = request.app.state
    service = RunStream(
        cast(async_sessionmaker[AsyncSession], state.session_factory),
        state.settings,
        state.dummy_password_hash,
    )
    raw = request.cookies.get(SESSION_COOKIE)
    page = await service.page(raw, run_id, cursor)  # Fail with HTTP status before headers.
    limiter = cast(RateLimiter, state.rate_limiter)
    await limiter.check(
        [
            Limit("run-stream:minute:" + str(page.user_id), 30, 60),
            Limit("run-stream:hour:" + str(page.user_id), 300, 3600),
        ]
    )
    return StreamingResponse(
        service.frames(raw, run_id, cursor, request.is_disconnected),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
