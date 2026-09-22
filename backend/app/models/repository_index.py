from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
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


class RepositoryIndex(Base):
    __tablename__ = "repository_indexes"
    __table_args__ = (
        UniqueConstraint("id", "import_job_id", name="uq_repository_index_source"),
        ForeignKeyConstraint(
            ["import_job_id", "repository_id"],
            ["import_jobs.id", "import_jobs.repository_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="ck_repository_index_status",
        ),
        Index(
            "uq_current_repository_index",
            "repository_id",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current = 1"),
        ),
        Index("ix_repository_indexes_dispatch", "status", "available_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    repository_id: Mapped[UUID]
    import_job_id: Mapped[UUID]
    commit_sha: Mapped[str] = mapped_column(String(40))
    pipeline_version: Mapped[str] = mapped_column(String(100))
    symbol_count: Mapped[int] = mapped_column(default=0, server_default="0")
    chunk_count: Mapped[int] = mapped_column(default=0, server_default="0")
    diagnostics: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    status: Mapped[str] = mapped_column(String(20), default="queued", server_default="queued")
    stage: Mapped[str] = mapped_column(String(40), default="queued", server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    files_scanned: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    files_stored: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    files_skipped: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
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
