from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_db
from app.api.routes.indexes import Reader, Writer
from app.core.rate_limits import RateLimiter
from app.embeddings.provider import EmbeddingProvider
from app.retrieval.postgres import PostgresCandidates
from app.schemas.health import ErrorResponse
from app.schemas.index import IndexAction
from app.schemas.search import (
    PrepareRequest,
    SearchJobResponse,
    SearchRequest,
    SearchResponse,
    SearchState,
)
from app.services.search import SearchService
from app.services.search_preparation import PreparationService

router = APIRouter(
    prefix="/repositories/{repository_id}/search",
    tags=["retrieval"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 429, 502, 503)},
)


def get_preparation(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> PreparationService:
    return PreparationService(
        db, cast(RateLimiter, request.app.state.rate_limiter), request.app.state.settings
    )


def get_search(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> SearchService:
    return SearchService(
        db,
        PostgresCandidates(db),
        cast(RateLimiter, request.app.state.rate_limiter),
        request.app.state.settings,
        cast(EmbeddingProvider | None, request.app.state.embedding_provider),
    )


Preparation = Annotated[PreparationService, Depends(get_preparation)]
Search = Annotated[SearchService, Depends(get_search)]


@router.get("", response_model=SearchState)
async def state(repository_id: UUID, identity: Reader, service: Preparation) -> SearchState:
    return await service.state(identity.user.id, repository_id)


@router.post(
    "/prepare", response_model=SearchJobResponse, responses={202: {"model": SearchJobResponse}}
)
async def prepare(
    repository_id: UUID,
    data: PrepareRequest,
    identity: Writer,
    service: Preparation,
    response: Response,
) -> SearchJobResponse:
    result, created = await service.start(identity.user.id, repository_id, data.mode)
    response.status_code = 202 if created else 200
    return result


@router.post("/cancel", status_code=204)
async def cancel(
    repository_id: UUID, data: IndexAction, identity: Writer, service: Preparation
) -> Response:
    await service.cancel(identity.user.id, repository_id)
    return Response(status_code=204)


@router.post("/query", response_model=SearchResponse)
async def query(
    repository_id: UUID, data: SearchRequest, identity: Writer, service: Search
) -> SearchResponse:
    # POST avoids source questions in URL/proxy logs and authorizes possible provider spend.
    return await service.search(identity.user.id, repository_id, data)
