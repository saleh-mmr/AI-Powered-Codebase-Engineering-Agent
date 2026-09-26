"""Commit attempts before calls and usage independently of answer publication."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError
from app.models import AnswerRun, UsageReceipt


class ReceiptWriter:
    def __init__(
        self, factory: async_sessionmaker[AsyncSession], run_id: UUID, lease_token: UUID
    ) -> None:
        self.factory, self.run_id, self.lease_token = factory, run_id, lease_token

    async def begin(self, kind: str, model: str, input_rate: float, output_rate: float = 0) -> UUID:
        async with self.factory() as db:
            # Serialize with cancellation/deletion; no network call inside this transaction.
            run = await db.scalar(
                select(AnswerRun).where(AnswerRun.id == self.run_id).with_for_update()
            )
            if (
                run is None
                or run.status != "running"
                or run.lease_token != self.lease_token
                or run.lease_expires_at is None
                or run.lease_expires_at.replace(tzinfo=UTC) <= datetime.now(UTC)
            ):
                raise AppError("answer_inactive", "Answer run is no longer active.", 409)
            receipt_id = uuid4()
            db.add(
                UsageReceipt(
                    id=receipt_id,
                    run_id=self.run_id,
                    kind=kind,
                    model=model,
                    input_rate=Decimal(str(input_rate)),
                    output_rate=Decimal(str(output_rate)),
                )
            )
            await db.commit()
            return receipt_id

    async def finish(self, receipt_id: UUID, input_tokens: int, output_tokens: int) -> None:
        if (
            type(input_tokens) is not int
            or type(output_tokens) is not int
            or min(input_tokens, output_tokens) < 0
        ):
            raise AppError("usage_invalid", "Provider usage was invalid.", 502)
        async with self.factory() as db:
            row = await db.get(UsageReceipt, receipt_id)
            if row is None:
                return  # Parent deleted; never recreate retained data.
            cost = (input_tokens * row.input_rate + output_tokens * row.output_rate) / Decimal(
                1000000
            )
            await db.execute(
                update(UsageReceipt)
                .where(UsageReceipt.id == receipt_id, UsageReceipt.input_tokens.is_(None))
                .values(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=cost,
                    finished_at=datetime.now(UTC),
                )
            )
            await db.commit()  # Also allowed after cancellation; this does not publish an answer.
