import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.generation.history import HistoryTurn
from app.jobs.answer_config import config_hash
from app.jobs.answer_preview import PreviewWriter
from app.models import AnswerRun, Conversation
from app.repositories.conversation import ConversationStore
from app.repositories.run_event import append_state
from app.schemas.answer import AnswerRequest
from app.services.answers import AnswerService
from app.services.usage_receipts import ReceiptWriter

logger = logging.getLogger("repopilot.answer_worker")


async def fail_run(
    factory: async_sessionmaker[AsyncSession], run_id: UUID, token: UUID, code: str, message: str
) -> None:
    async with factory() as db:
        changed = await db.scalar(
            update(AnswerRun)
            .where(
                AnswerRun.id == run_id,
                AnswerRun.status == "running",
                AnswerRun.lease_token == token,
            )
            .values(
                status="failed",
                finished_at=datetime.now(UTC),
                lease_token=None,
                lease_expires_at=None,
                error_code=code,
                error_message=message,
            )
            .returning(AnswerRun.id)
        )
        if changed is not None:
            await append_state(db, run_id)
        await db.commit()


async def run_answer(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    settings: Settings,
    build_answer: Callable[[AsyncSession], AnswerService],
) -> None:
    now, token = datetime.now(UTC), uuid4()
    async with factory() as db:
        claimed = await db.scalar(
            update(AnswerRun)
            .where(
                AnswerRun.id == run_id,
                AnswerRun.status == "queued",
                AnswerRun.created_at > now - timedelta(hours=1),
            )
            .values(
                status="running",
                usage_state="unknown",
                started_at=now,
                lease_token=token,
                lease_expires_at=now + timedelta(seconds=180),
            )
            .returning(AnswerRun.id)
        )
        if claimed is None:
            return  # Duplicate broker delivery is a no-op, including completed/expired runs.
        await append_state(db, run_id)
        await db.commit()
    try:
        async with factory() as db:
            run = await db.get(AnswerRun, run_id)
            if run is None or run.status != "running" or run.lease_token != token:
                return
            conversation = await db.get(Conversation, run.conversation_id)
            if conversation is None:
                return
            conversation_id, user_id, repository_id = (
                conversation.id,
                conversation.user_id,
                conversation.repository_id,
            )
            source_id, question = run.source_index_id, run.question
            request = AnswerRequest(question=question, mode=run.mode)
            if run.config_hash != config_hash(settings):
                raise AppError(
                    "answer_config_changed",
                    "Model configuration changed after submission. Submit a new run.",
                    409,
                )
            history = [HistoryTurn.model_validate(turn) for turn in run.history]
            await db.commit()
            preview = PreviewWriter(factory, run_id, token)
            service = build_answer(db)
            service.receipts = ReceiptWriter(factory, run_id, token)
            service.search.receipts = service.receipts
            answer = await service.answer(
                user_id,
                repository_id,
                request,
                expected_source_id=source_id,
                history=history,
                on_delta=preview.delta,
            )
            answer = answer.model_copy(update={"answer_id": run_id})
            # Lock conversation before run to match cascade-delete lock ordering.
            await db.execute(
                select(Conversation.id).where(Conversation.id == conversation_id).with_for_update()
            )
            published = await db.scalar(
                update(AnswerRun)
                .execution_options(synchronize_session=False)
                .where(
                    AnswerRun.id == run_id,
                    AnswerRun.status == "running",
                    AnswerRun.lease_token == token,
                    AnswerRun.lease_expires_at > datetime.now(UTC),
                )
                .values(
                    status="completed",
                    usage_state="recorded",
                    input_tokens=answer.input_tokens,
                    output_tokens=answer.output_tokens,
                    estimated_cost_usd=answer.estimated_generation_cost_usd
                    + answer.estimated_retrieval_cost_usd,
                    finished_at=datetime.now(UTC),
                    lease_token=None,
                    lease_expires_at=None,
                )
                .returning(AnswerRun.id)
            )
            if published is None:
                return  # Cancellation, expiry or deletion fences late results.
            await ConversationStore(db).append_pair(user_id, conversation_id, question, answer)
            await append_state(db, run_id)
            await db.commit()  # State, event, usage and both messages publish atomically.
        logger.info("answer_run_completed", extra={"job_id": str(run_id)})
    except Exception as exc:
        code = exc.code if isinstance(exc, AppError) else "answer_worker_error"
        message = (
            exc.message
            if isinstance(exc, AppError)
            else "The answer worker failed. Check status before retrying."
        )
        logger.warning(
            "answer_run_failed",
            extra={"job_id": str(run_id), "error_code": code, "error_type": type(exc).__name__},
        )
        await fail_run(factory, run_id, token, code, message)
