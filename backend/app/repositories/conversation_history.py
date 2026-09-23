from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.generation.history import HistoryTurn, bounded_history
from app.models import Message
from app.repositories.conversation import ConversationStore
from app.schemas.answer import AnswerResponse


async def snapshot_history(
    db: AsyncSession, user_id: UUID, conversation_id: UUID, source_id: UUID
) -> list[HistoryTurn]:
    await ConversationStore(db).owned(user_id, conversation_id)
    rows = list(
        (
            await db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.position.desc())
                .limit(6)
            )
        ).all()
    )
    selected: list[HistoryTurn] = []
    # Stop at an ineligible pair so omitted context does not silently join unrelated turns.
    for offset in range(0, len(rows) - 1, 2):
        answer_row, question_row = rows[offset : offset + 2]
        if (
            answer_row.role != "assistant"
            or question_row.role != "user"
            or answer_row.turn_id != question_row.turn_id
            or answer_row.position != question_row.position + 1
        ):
            break
        answer = AnswerResponse.model_validate(answer_row.answer)
        if answer.source_index_id != source_id or answer.status != "answered":
            break
        text = "\n".join(claim.text for claim in answer.claims)
        if not text or len(text) > 8000:
            break
        selected.append(
            HistoryTurn(turn_id=answer_row.turn_id, question=question_row.content, answer=text)
        )
    return bounded_history(list(reversed(selected)))
