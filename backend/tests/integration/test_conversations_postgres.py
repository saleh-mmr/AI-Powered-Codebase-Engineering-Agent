import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.database.session import create_engine
from app.models import Conversation, Message, Repository, User
from app.repositories.conversation import ConversationStore
from app.schemas.answer import AnswerResponse


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1", reason="requires migrated isolated PostgreSQL"
)
def test_concurrent_transcript_appends_on_postgres():
    async def scenario():
        settings = Settings()
        assert settings.database_url.get_secret_value().split("?")[0].endswith("_test")
        engine = create_engine(settings)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        user_id, repo_id, conversation_id = uuid4(), uuid4(), uuid4()
        try:
            async with factory() as db:
                db.add(
                    User(
                        id=user_id,
                        email=f"{user_id}@example.com",
                        name="Test",
                        password_hash="unused",
                    )
                )
                await db.flush()
                db.add(
                    Repository(
                        id=repo_id,
                        user_id=user_id,
                        source_key=str(repo_id),
                        owner="fixture",
                        name="fixture",
                    )
                )
                await db.flush()
                db.add(
                    Conversation(
                        id=conversation_id,
                        user_id=user_id,
                        repository_id=repo_id,
                        title="Concurrency",
                    )
                )
                await db.commit()

            async def append():
                answer = AnswerResponse(
                    answer_id=uuid4(),
                    status="insufficient_evidence",
                    claims=[],
                    limitation="No evidence.",
                    evidence=[],
                    source_index_id=uuid4(),
                    search_index_id=uuid4(),
                    commit_sha="a" * 40,
                    retrieval_mode="keyword",
                    retrieval_version="test",
                    embedding_profile="none",
                    context_tokens=0,
                    context_omitted=0,
                    prompt_version="test",
                    prompt_hash="a" * 64,
                    model=None,
                    input_tokens=0,
                    output_tokens=0,
                    estimated_generation_cost_usd=0,
                    estimated_retrieval_cost_usd=0,
                    duration_ms=1,
                )
                async with factory() as db:
                    await ConversationStore(db).append_pair(
                        user_id, conversation_id, "question", answer
                    )
                    await db.commit()

            await asyncio.gather(append(), append(), append())
            async with factory() as db:
                messages = list(
                    (
                        await db.scalars(
                            select(Message)
                            .where(Message.conversation_id == conversation_id)
                            .order_by(Message.position)
                        )
                    ).all()
                )
                assert [m.position for m in messages] == list(range(1, 7))
                for i in (0, 2, 4):
                    assert messages[i].turn_id == messages[i + 1].turn_id
                    assert [messages[i].role, messages[i + 1].role] == ["user", "assistant"]
                conversation = await db.get(Conversation, conversation_id)
                assert conversation.message_count == 6
        finally:
            async with engine.begin() as conn:
                await conn.execute(delete(User).where(User.id == user_id))
            await engine.dispose()

    asyncio.run(scenario())
