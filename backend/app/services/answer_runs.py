import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.rate_limits import Limit, RateLimiter
from app.jobs.answer_config import config_hash
from app.models import AnswerRun, Conversation
from app.repositories.answer_run import RunStore
from app.repositories.conversation import ConversationStore
from app.schemas.answer_run import RunList, RunRequest, RunResponse
from app.services.search_preparation import PreparationService


class RunService:
    def __init__(self, db: AsyncSession, limiter: RateLimiter, settings: Settings) -> None:
        self.db, self.limiter, self.settings = db, limiter, settings
        self.store = RunStore(db)

    async def list(self, user_id: UUID, conversation_id: UUID) -> RunList:
        await ConversationStore(self.db).owned(user_id, conversation_id)
        return RunList(
            items=[
                RunResponse.model_validate(run) for run in await self.store.recent(conversation_id)
            ]
        )

    async def get(self, user_id: UUID, run_id: UUID) -> RunResponse:
        return RunResponse.model_validate(await self.store.owned(user_id, run_id))

    async def submit(
        self, user_id: UUID, conversation_id: UUID, data: RunRequest
    ) -> tuple[RunResponse, bool]:
        conversation = await ConversationStore(self.db).owned(user_id, conversation_id)
        repository_id = conversation.repository_id
        await self.db.execute(
            select(Conversation.id).where(Conversation.id == conversation_id).with_for_update()
        )
        fingerprint = sha256(
            json.dumps({"question": data.question, "mode": data.mode}, sort_keys=True).encode()
        ).hexdigest()
        existing = await self.store.by_key(conversation_id, data.request_key)
        if existing:
            return self.replay(existing, fingerprint), False
        if not self.settings.answers_enabled:
            raise AppError(
                "answers_disabled", "AI answers are disabled in server configuration.", 409
            )
        # Re-read the current count after taking the row lock.
        count = await self.db.scalar(
            select(Conversation.message_count).where(Conversation.id == conversation_id)
        )
        if count is None:
            raise AppError("not_found", "Conversation not found.", 404)
        if count >= 200:
            raise AppError("conversation_full", "This conversation is full. Create another.", 409)
        active = await self.db.scalar(
            select(AnswerRun.id).where(
                AnswerRun.conversation_id == conversation_id,
                AnswerRun.status.in_(["queued", "running"]),
            )
        )
        if active:
            raise AppError(
                "answer_active", "This conversation already has an active answer run.", 409
            )
        total = await self.db.scalar(
            select(func.count())
            .select_from(AnswerRun)
            .where(AnswerRun.conversation_id == conversation_id)
        )
        if total is not None and total >= 1000:
            raise AppError(
                "run_limit", "This conversation has reached its run limit. Create another.", 409
            )
        preparation = PreparationService(self.db, self.limiter, self.settings)
        source = await preparation.source(user_id, repository_id)
        state = await preparation.state(user_id, repository_id)
        if (data.mode == "keyword" and not state.keyword) or (
            data.mode == "hybrid" and (not state.hybrid or not self.settings.embeddings_enabled)
        ):
            raise AppError("search_required", "Prepare the selected search mode first.", 409)
        await self.limiter.check(
            [
                Limit("answer-submit:minute:" + str(user_id), 10, 60),
                Limit("answer-submit:day:" + str(user_id), 60, 86400),
            ]
        )
        run = AnswerRun(
            conversation_id=conversation_id,
            request_key=data.request_key,
            request_hash=fingerprint,
            question=data.question,
            mode=data.mode,
            source_index_id=source.id,
            config_hash=config_hash(self.settings),
            model=self.settings.answer_model,
        )
        self.db.add(run)
        try:
            await self.db.flush()
            response = RunResponse.model_validate(run)
            await self.db.commit()
            return response, True
        except IntegrityError:
            await self.db.rollback()
            existing = await self.store.by_key(conversation_id, data.request_key)
            if existing:
                return self.replay(existing, fingerprint), False
            raise AppError(
                "answer_active", "Another submission won. Refresh run status.", 409
            ) from None

    @staticmethod
    def replay(run: AnswerRun, fingerprint: str) -> RunResponse:
        if run.request_hash != fingerprint:
            raise AppError(
                "idempotency_conflict",
                "This request key was already used for another question or mode.",
                409,
            )
        return RunResponse.model_validate(run)

    async def cancel(self, user_id: UUID, run_id: UUID) -> RunResponse:
        await self.store.owned(user_id, run_id)
        found = await self.db.scalar(
            update(AnswerRun)
            .where(AnswerRun.id == run_id, AnswerRun.status.in_(["queued", "running"]))
            .values(
                status="cancelled",
                finished_at=datetime.now(UTC),
                lease_token=None,
                lease_expires_at=None,
            )
            .returning(AnswerRun.id)
        )
        if found is None:
            raise AppError(
                "answer_terminal", "This run has already finished. Refresh its status.", 409
            )
        await self.db.commit()
        self.db.expire_all()
        return await self.get(user_id, run_id)
