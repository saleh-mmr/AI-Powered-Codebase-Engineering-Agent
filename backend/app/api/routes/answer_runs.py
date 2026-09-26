from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_db
from app.api.routes.indexes import Reader, Writer
from app.core.rate_limits import RateLimiter
from app.schemas.answer_run import RunList, RunRequest, RunResponse
from app.schemas.health import ErrorResponse
from app.schemas.index import IndexAction
from app.schemas.usage_receipt import RunUsage
from app.services.answer_runs import RunService

router = APIRouter(
    tags=["answer runs"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 429, 503)},
)


def get_runs(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> RunService:
    return RunService(
        db, cast(RateLimiter, request.app.state.rate_limiter), request.app.state.settings
    )


Runs = Annotated[RunService, Depends(get_runs)]


@router.get("/conversations/{conversation_id}/runs", response_model=RunList)
async def recent(conversation_id: UUID, identity: Reader, service: Runs) -> RunList:
    return await service.list(identity.user.id, conversation_id)


@router.post(
    "/conversations/{conversation_id}/runs",
    response_model=RunResponse,
    responses={202: {"model": RunResponse}},
)
async def submit(
    conversation_id: UUID, data: RunRequest, identity: Writer, service: Runs, response: Response
) -> RunResponse:
    result, created = await service.submit(identity.user.id, conversation_id, data)
    response.status_code = 202 if created else 200
    return result


@router.get("/answer-runs/{run_id}", response_model=RunResponse)
async def get(run_id: UUID, identity: Reader, service: Runs) -> RunResponse:
    return await service.get(identity.user.id, run_id)


@router.post("/answer-runs/{run_id}/cancel", response_model=RunResponse)
async def cancel(run_id: UUID, data: IndexAction, identity: Writer, service: Runs) -> RunResponse:
    return await service.cancel(identity.user.id, run_id)


@router.get("/answer-runs/{run_id}/usage", response_model=RunUsage)
async def usage(run_id: UUID, identity: Reader, service: Runs) -> RunUsage:
    return await service.usage(identity.user.id, run_id)
