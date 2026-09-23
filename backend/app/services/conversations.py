from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rate_limits import Limit, RateLimiter
from app.models import Conversation, Repository
from app.repositories.conversation import ConversationStore
from app.repositories.repository import RepositoryStore
from app.schemas.answer import AnswerRequest, AnswerResponse
from app.schemas.conversation import (
    ConversationCreate,
    ConversationList,
    ConversationResponse,
    MessagePage,
    MessageResponse,
)
from app.services.answers import AnswerService


class ConversationService:
    def __init__(self, db: AsyncSession, limiter: RateLimiter) -> None:
        self.db, self.limiter = db, limiter
        self.store = ConversationStore(db)

    async def list(self, user_id: UUID, repository_id: UUID) -> ConversationList:
        await RepositoryStore(self.db).owned(user_id, repository_id)
        return ConversationList(
            items=[
                ConversationResponse.model_validate(c)
                for c in await self.store.list_owned(user_id, repository_id)
            ]
        )

    async def create(
        self, user_id: UUID, repository_id: UUID, data: ConversationCreate
    ) -> ConversationResponse:
        await RepositoryStore(self.db).owned(user_id, repository_id)
        await self.db.execute(
            select(Repository.id)
            .where(Repository.id == repository_id, Repository.user_id == user_id)
            .with_for_update()
        )
        count = await self.db.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.repository_id == repository_id)
        )
        if count is not None and count >= 100:
            raise AppError(
                "conversation_limit",
                "This repository has 100 conversations. Delete one first.",
                409,
            )
        await self.limiter.check([Limit("conversations:create:" + str(user_id), 20, 3600)])
        conversation = Conversation(user_id=user_id, repository_id=repository_id, title=data.title)
        self.db.add(conversation)
        await self.db.flush()
        response = ConversationResponse.model_validate(conversation)
        await self.db.commit()
        return response

    async def detail(self, user_id: UUID, conversation_id: UUID) -> ConversationResponse:
        return ConversationResponse.model_validate(await self.store.owned(user_id, conversation_id))

    async def messages(
        self, user_id: UUID, conversation_id: UUID, before: int | None
    ) -> MessagePage:
        await self.store.owned(user_id, conversation_id)
        rows, cursor = await self.store.messages(conversation_id, before)
        return MessagePage(
            items=[MessageResponse.model_validate(row) for row in rows], next_before=cursor
        )

    async def remove(self, user_id: UUID, conversation_id: UUID) -> None:
        await self.store.owned(user_id, conversation_id)
        await self.db.execute(
            delete(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )
        await self.db.commit()

    async def ask(
        self, user_id: UUID, conversation_id: UUID, data: AnswerRequest, answers: AnswerService
    ) -> AnswerResponse:
        conversation = await self.store.owned(user_id, conversation_id)
        if conversation.message_count >= 200:
            raise AppError("conversation_full", "This conversation is full. Create another.", 409)
        repository_id = conversation.repository_id
        await self.db.commit()
        # Reuse M6 validation/authorization; history is not silently added to the prompt.
        answer = await answers.answer(user_id, repository_id, data)
        await self.store.append_pair(user_id, conversation_id, data.question, answer)
        await self.db.commit()
        return answer
