"""One durable attempt per provider purpose; no prompts or source content."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class UsageReceipt(Base):
    __tablename__ = "usage_receipts"
    __table_args__ = (
        UniqueConstraint("run_id", "kind", name="uq_receipt_run_kind"),
        CheckConstraint("kind IN ('generation','query_embedding')", name="ck_receipt_kind"),
        CheckConstraint("input_rate >= 0 AND output_rate >= 0", name="ck_receipt_rates"),
        CheckConstraint(
            "(input_tokens IS NULL AND output_tokens IS NULL AND estimated_cost_usd IS NULL) "
            "OR (input_tokens >= 0 AND output_tokens >= 0 AND estimated_cost_usd >= 0 "
            "AND input_tokens IS NOT NULL AND output_tokens IS NOT NULL "
            "AND estimated_cost_usd IS NOT NULL)",
            name="ck_receipt_usage",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("answer_runs.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(200))
    input_rate: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    output_rate: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
