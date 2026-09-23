from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_db
from app.api.routes.indexes import Reader, Writer
from app.api.routes.search import get_search
from app.core.rate_limits import RateLimiter
from app.generation.contracts import AnswerProvider
from app.schemas.answer import AnswerRequest, AnswerResponse, AnswerSettings
from app.schemas.health import ErrorResponse
from app.services.answers import AnswerService
from app.services.search import SearchService

router = APIRouter(
    prefix="/repositories/{repository_id}/answers",
    tags=["answers"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 429, 502, 503)},
)


def get_answers(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Annotated[SearchService, Depends(get_search)],
) -> AnswerService:
    return AnswerService(
        db,
        search,
        cast(RateLimiter, request.app.state.rate_limiter),
        request.app.state.settings,
        cast(AnswerProvider | None, request.app.state.answer_provider),
    )


Answers = Annotated[AnswerService, Depends(get_answers)]


@router.get("", response_model=AnswerSettings)
async def settings(repository_id: UUID, identity: Reader, service: Answers) -> AnswerSettings:
    return await service.configuration(identity.user.id, repository_id)


@router.post("", response_model=AnswerResponse)
async def answer(
    repository_id: UUID, data: AnswerRequest, identity: Writer, service: Answers
) -> AnswerResponse:
    return await service.answer(identity.user.id, repository_id, data)
