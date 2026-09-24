import asyncio
import logging
from time import perf_counter
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.rate_limits import Limit, RateLimiter
from app.generation.context import (
    INSTRUCTIONS,
    PROMPT_HASH,
    PROMPT_VERSION,
    build_context,
    validate_citations,
)
from app.generation.contracts import (
    AnswerProvider,
    DeltaSink,
    GenerationResult,
    StreamingAnswerProvider,
)
from app.generation.history import (
    HISTORY_POLICY,
    HistoryTurn,
    bounded_history,
    history_tokens,
    retrieval_question,
)
from app.repositories.repository import RepositoryStore
from app.schemas.answer import AnswerRequest, AnswerResponse, AnswerSettings
from app.schemas.search import SearchRequest
from app.services.search import SearchService

logger = logging.getLogger("repopilot.answers")


class AnswerService:
    def __init__(
        self,
        db: AsyncSession,
        search: SearchService,
        limiter: RateLimiter,
        settings: Settings,
        provider: AnswerProvider | None,
    ) -> None:
        self.db, self.search, self.limiter = db, search, limiter
        self.settings, self.provider = settings, provider

    async def configuration(self, user_id: UUID, repository_id: UUID) -> AnswerSettings:
        await RepositoryStore(self.db).owned(user_id, repository_id)
        return AnswerSettings(
            enabled=self.settings.answers_enabled,
            embeddings_enabled=self.settings.embeddings_enabled,
            model=self.settings.answer_model,
            max_output_tokens=self.settings.answer_max_output_tokens,
            input_price_per_million=self.settings.answer_input_price_per_million,
            output_price_per_million=self.settings.answer_output_price_per_million,
        )

    async def answer(
        self,
        user_id: UUID,
        repository_id: UUID,
        request: AnswerRequest,
        expected_source_id: UUID | None = None,
        history: list[HistoryTurn] | None = None,
        on_delta: DeltaSink | None = None,
    ) -> AnswerResponse:
        answer_id = uuid4()
        started = perf_counter()
        try:
            async with asyncio.timeout(60):
                return await self._answer(
                    answer_id,
                    started,
                    user_id,
                    repository_id,
                    request,
                    expected_source_id,
                    bounded_history(history or []),
                    on_delta,
                )
        except TimeoutError:
            logger.warning(
                "answer_failed", extra={"answer_id": str(answer_id), "error_code": "answer_timeout"}
            )
            raise AppError(
                "answer_timeout", "Answer request timed out. Retry later.", 503
            ) from None
        except ValidationError:
            logger.warning(
                "answer_failed", extra={"answer_id": str(answer_id), "error_code": "model_invalid"}
            )
            raise AppError("model_invalid", "Model output failed validation.", 502) from None
        except AppError as exc:
            logger.warning(
                "answer_failed", extra={"answer_id": str(answer_id), "error_code": exc.code}
            )
            raise

    async def _answer(
        self,
        answer_id: UUID,
        started: float,
        user_id: UUID,
        repository_id: UUID,
        request: AnswerRequest,
        expected_source_id: UUID | None,
        history: list[HistoryTurn],
        on_delta: DeltaSink | None,
    ) -> AnswerResponse:
        # Authorize before checking configuration, using quotas, or sending any data externally.
        await RepositoryStore(self.db).owned(user_id, repository_id)
        if not self.settings.answers_enabled or self.provider is None:
            raise AppError(
                "answers_disabled", "AI answers are disabled in server configuration.", 409
            )
        await self.limiter.check(
            [
                Limit("answer:user:minute:" + str(user_id), 5, 60),
                Limit("answer:user:day:" + str(user_id), 30, 86400),
                Limit("answer:deployment:day", self.settings.answer_daily_request_limit, 86400),
            ]
        )
        retrieved = await self.search.search(
            user_id,
            repository_id,
            SearchRequest(
                query=retrieval_question(request.question, history),
                mode=request.mode,
                top_k=8,
                context_token_budget=6000,
            ),
        )
        # Search's final source load starts another read transaction. Release it before generation.
        await self.db.commit()
        if expected_source_id is not None and retrieved.source_index_id != expected_source_id:
            raise AppError(
                "answer_source_changed",
                "The source index changed after submission. Submit a new run.",
                409,
            )
        included: list[HistoryTurn] = []
        result: GenerationResult | None = None
        if retrieved.context:
            payload, included = build_context(request.question, retrieved.context, history)
            logger.info(
                "answer_model_requested",
                extra={
                    "answer_id": str(answer_id),
                    "model": self.provider.model,
                    "result_count": len(retrieved.context),
                },
            )
            if on_delta is not None and isinstance(self.provider, StreamingAnswerProvider):
                generated = await self.provider.generate_stream(INSTRUCTIONS, payload, on_delta)
            else:
                generated = await self.provider.generate(INSTRUCTIONS, payload)
            # Revalidate the provider boundary even when another adapter is introduced later.
            result = GenerationResult.model_validate(generated.model_dump())
            cost = (
                result.input_tokens * self.settings.answer_input_price_per_million
                + result.output_tokens * self.settings.answer_output_price_per_million
            ) / 1000000
            # Usage is recorded before citation checks: rejected answers can still cost money.
            logger.info(
                "answer_model_completed",
                extra={
                    "answer_id": str(answer_id),
                    "model": result.model,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "estimated_cost_usd": cost,
                },
            )
            if result.draft:
                validate_citations(result.draft, retrieved.context)
        else:
            cost = 0.0
        draft = result.draft if result else None
        status = (
            "refused"
            if result and result.refused
            else (draft.status if draft else "insufficient_evidence")
        )
        limitation = (
            draft.limitation
            if draft
            else (
                "The model declined this request."
                if result
                else "No source evidence was retrieved. Try a function name or hybrid search."
            )
        )
        response = AnswerResponse(
            answer_id=answer_id,
            status=status,
            claims=draft.claims if draft else [],
            limitation=limitation,
            evidence=retrieved.context,
            source_index_id=retrieved.source_index_id,
            search_index_id=retrieved.search_index_id,
            commit_sha=retrieved.commit_sha,
            retrieval_mode=retrieved.mode,
            retrieval_version=retrieved.pipeline_version,
            embedding_profile=retrieved.provider_profile,
            context_tokens=retrieved.context_tokens,
            context_omitted=retrieved.context_omitted,
            prompt_version=PROMPT_VERSION,
            prompt_hash=PROMPT_HASH,
            model=result.model if result else None,
            input_tokens=result.input_tokens if result else 0,
            output_tokens=result.output_tokens if result else 0,
            estimated_generation_cost_usd=cost,
            estimated_retrieval_cost_usd=retrieved.estimated_query_cost_usd,
            history_turn_ids=[turn.turn_id for turn in included],
            history_tokens=history_tokens(included),
            history_policy=HISTORY_POLICY if history else "none",
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )
        logger.info(
            "answer_completed",
            extra={
                "answer_id": str(answer_id),
                "duration_ms": response.duration_ms,
                "result_count": len(response.claims),
            },
        )
        return response
