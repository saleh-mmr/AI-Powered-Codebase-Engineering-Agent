from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AnswerRun(Base):
    __tablename__ = "answer_runs"
    __table_args__ = (
        UniqueConstraint("conversation_id", "request_key", name="uq_answer_run_request"),
        Index(
            "uq_answer_run_active",
            "conversation_id",
            unique=True,
            postgresql_where=text("status IN ('queued','running')"),
            sqlite_where=text("status IN ('queued','running')"),
        ),
        Index("ix_answer_runs_dispatch", "status", "created_at"),
        CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="ck_answer_run_status",
        ),
        CheckConstraint("length(preview_text) <= 8000", name="ck_run_preview_length"),
        CheckConstraint(
            "preview_revision >= 0 AND preview_revision <= 256", name="ck_run_preview_revision"
        ),
        CheckConstraint("mode IN ('keyword','hybrid')", name="ck_answer_run_mode"),
        CheckConstraint(
            "usage_state IN ('not_started','unknown','recorded')", name="ck_answer_run_usage"
        ),
        CheckConstraint("input_tokens IS NULL OR input_tokens >= 0", name="ck_answer_run_input"),
        CheckConstraint("output_tokens IS NULL OR output_tokens >= 0", name="ck_answer_run_output"),
        CheckConstraint(
            "estimated_cost_usd IS NULL OR estimated_cost_usd >= 0", name="ck_answer_run_cost"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    request_key: Mapped[UUID] = mapped_column(nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64))
    question: Mapped[str] = mapped_column(Text)
    preview_text: Mapped[str] = mapped_column(Text, server_default="")
    preview_revision: Mapped[int] = mapped_column(Integer, server_default="0")
    history: Mapped[list[dict[str, object]]] = mapped_column(JSON, server_default="[]")
    mode: Mapped[str] = mapped_column(String(20))
    source_index_id: Mapped[UUID] = mapped_column(nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), server_default="queued")
    receipt_version: Mapped[int] = mapped_column(Integer, server_default="0")
    usage_state: Mapped[str] = mapped_column(String(20), server_default="not_started")
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(300))
    lease_token: Mapped[UUID | None] = mapped_column()
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
