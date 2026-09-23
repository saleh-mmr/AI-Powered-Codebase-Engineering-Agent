from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_db
from app.api.routes.answers import Answers
from app.api.routes.indexes import Reader, Writer
from app.core.rate_limits import RateLimiter
from app.schemas.answer import AnswerRequest, AnswerResponse
from app.schemas.conversation import (
    ConversationCreate,
    ConversationList,
    ConversationResponse,
    MessagePage,
)
from app.schemas.health import ErrorResponse
from app.services.conversations import ConversationService

router = APIRouter(
    tags=["conversations"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 429, 502, 503)},
)


def get_conversations(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> ConversationService:
    return ConversationService(db, cast(RateLimiter, request.app.state.rate_limiter))


Conversations = Annotated[ConversationService, Depends(get_conversations)]


@router.get("/repositories/{repository_id}/conversations", response_model=ConversationList)
async def list_conversations(
    repository_id: UUID, identity: Reader, service: Conversations
) -> ConversationList:
    return await service.list(identity.user.id, repository_id)


@router.post(
    "/repositories/{repository_id}/conversations",
    response_model=ConversationResponse,
    status_code=201,
)
async def create_conversation(
    repository_id: UUID, data: ConversationCreate, identity: Writer, service: Conversations
) -> ConversationResponse:
    return await service.create(identity.user.id, repository_id, data)


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def detail(
    conversation_id: UUID, identity: Reader, service: Conversations
) -> ConversationResponse:
    return await service.detail(identity.user.id, conversation_id)


@router.get("/conversations/{conversation_id}/messages", response_model=MessagePage)
async def messages(
    conversation_id: UUID,
    identity: Reader,
    service: Conversations,
    before: Annotated[int | None, Query(ge=1)] = None,
) -> MessagePage:
    return await service.messages(identity.user.id, conversation_id, before)


@router.post(
    "/conversations/{conversation_id}/messages", response_model=AnswerResponse, status_code=201
)
async def ask(
    conversation_id: UUID,
    data: AnswerRequest,
    identity: Writer,
    service: Conversations,
    answers: Answers,
) -> AnswerResponse:
    return await service.ask(identity.user.id, conversation_id, data, answers)


@router.delete("/conversations/{conversation_id}", status_code=204)
async def remove(conversation_id: UUID, identity: Writer, service: Conversations) -> Response:
    await service.remove(identity.user.id, conversation_id)
    return Response(status_code=204)
