from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import current_identity, get_db, require_csrf
from app.core.rate_limits import RateLimiter
from app.schemas.health import ErrorResponse
from app.schemas.index import IndexAction, IndexedFilePage, IndexResponse, IndexState
from app.services.auth import Identity
from app.services.index import IndexService

router = APIRouter(
    prefix="/repositories/{repository_id}/index",
    tags=["indexing"],
    responses={s: {"model": ErrorResponse} for s in (401, 403, 404, 409, 422, 429, 503)},
)


def get_service(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> IndexService:
    return IndexService(db, cast(RateLimiter, request.app.state.rate_limiter))


Service = Annotated[IndexService, Depends(get_service)]
Reader = Annotated[Identity, Depends(current_identity)]
Writer = Annotated[Identity, Depends(require_csrf)]


@router.get("", response_model=IndexState)
async def state(repository_id: UUID, identity: Reader, service: Service) -> IndexState:
    return await service.state(identity.user.id, repository_id)


@router.post("", response_model=IndexResponse, responses={202: {"model": IndexResponse}})
async def start(
    repository_id: UUID, data: IndexAction, identity: Writer, service: Service, response: Response
) -> IndexResponse:
    result, created = await service.start(identity.user.id, repository_id)
    response.status_code = 202 if created else 200
    return result


@router.post("/cancel", status_code=204)
async def cancel(
    repository_id: UUID, data: IndexAction, identity: Writer, service: Service
) -> Response:
    await service.cancel(identity.user.id, repository_id)
    return Response(status_code=204)


@router.get("/files/{file_id}", response_model=IndexedFilePage)
async def file(
    repository_id: UUID,
    file_id: UUID,
    identity: Reader,
    service: Service,
    symbol_offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    chunk_offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> IndexedFilePage:
    return await service.file(identity.user.id, repository_id, file_id, symbol_offset, chunk_offset)
