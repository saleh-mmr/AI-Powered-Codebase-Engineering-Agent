from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class RunEvent(Base):
    __tablename__ = "answer_run_events"
    __table_args__ = (
        CheckConstraint("sequence >= 1 AND sequence <= 3", name="ck_run_event_sequence"),
        CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="ck_run_event_status",
        ),
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("answer_runs.id", ondelete="CASCADE"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
