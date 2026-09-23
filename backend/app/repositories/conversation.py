from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Conversation, Message, Repository
from app.schemas.answer import AnswerResponse


class ConversationStore:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def owned(self, user_id: UUID, conversation_id: UUID) -> Conversation:
        conversation = await self.db.scalar(
            select(Conversation)
            .join(Repository, Repository.id == Conversation.repository_id)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
                Repository.user_id == user_id,
            )
        )
        if conversation is None:
            raise AppError("not_found", "Conversation not found.", 404)
        return conversation

    async def list_owned(self, user_id: UUID, repository_id: UUID) -> list[Conversation]:
        return list(
            (
                await self.db.scalars(
                    select(Conversation)
                    .where(
                        Conversation.user_id == user_id, Conversation.repository_id == repository_id
                    )
                    .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
                    .limit(100)
                )
            ).all()
        )

    async def messages(
        self, conversation_id: UUID, before: int | None
    ) -> tuple[list[Message], int | None]:
        statement = select(Message).where(Message.conversation_id == conversation_id)
        if before is not None:
            statement = statement.where(Message.position < before)
        rows = list(
            (await self.db.scalars(statement.order_by(Message.position.desc()).limit(21))).all()
        )
        page = list(reversed(rows[:20]))
        return page, page[0].position if len(rows) > 20 else None

    async def append_pair(
        self, user_id: UUID, conversation_id: UUID, question: str, answer: AnswerResponse
    ) -> None:
        # A short atomic counter update allocates adjacent positions; no lock spans model I/O.
        count = await self.db.scalar(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
                Conversation.message_count <= 198,
            )
            .values(message_count=Conversation.message_count + 2, updated_at=func.now())
            .returning(Conversation.message_count)
        )
        if count is None:
            await self.owned(user_id, conversation_id)
            raise AppError("conversation_full", "This conversation is full. Create another.", 409)
        self.db.add_all(
            [
                Message(
                    conversation_id=conversation_id,
                    turn_id=answer.answer_id,
                    position=count - 1,
                    role="user",
                    content=question,
                    token_count=None,
                    answer=None,
                ),
                Message(
                    conversation_id=conversation_id,
                    turn_id=answer.answer_id,
                    position=count,
                    role="assistant",
                    content="\n\n".join(
                        [c.text for c in answer.claims]
                        + ([answer.limitation] if answer.limitation else [])
                    ),
                    token_count=answer.output_tokens if answer.model else None,
                    answer=answer.model_dump(mode="json"),
                ),
            ]
        )
        await self.db.flush()
