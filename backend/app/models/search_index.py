from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SearchIndex(Base):
    __tablename__ = "search_indexes"
    __table_args__ = (
        UniqueConstraint("id", "source_index_id", name="uq_search_index_source"),
        ForeignKeyConstraint(
            ["source_index_id", "repository_id"],
            ["repository_indexes.id", "repository_indexes.repository_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("mode IN ('keyword','hybrid')", name="ck_search_mode"),
        CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="ck_search_index_status",
        ),
        Index(
            "uq_current_search_index",
            "repository_id",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current = 1"),
        ),
        Index("ix_search_indexes_dispatch", "status", "available_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    repository_id: Mapped[UUID]
    source_index_id: Mapped[UUID]
    commit_sha: Mapped[str] = mapped_column(String(40))
    pipeline_version: Mapped[str] = mapped_column(String(100))
    mode: Mapped[str] = mapped_column(String(20))
    provider_profile: Mapped[str] = mapped_column(String(120))
    documents_stored: Mapped[int] = mapped_column(default=0, server_default="0")
    reserved_tokens: Mapped[int] = mapped_column(default=0, server_default="0")
    input_tokens: Mapped[int] = mapped_column(default=0, server_default="0")
    token_budget: Mapped[int]
    price_per_million: Mapped[float]

    is_current: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    status: Mapped[str] = mapped_column(String(20), default="queued", server_default="queued")
    stage: Mapped[str] = mapped_column(String(40), default="queued", server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(300))
    lease_token: Mapped[UUID | None]
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
