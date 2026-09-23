from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.answer import AnswerRequest


class RunRequest(AnswerRequest):
    request_key: UUID


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    conversation_id: UUID
    request_key: UUID
    question: str
    mode: Literal["keyword", "hybrid"]
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    model: str
    source_index_id: UUID
    usage_state: Literal["not_started", "unknown", "recorded"]
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunList(BaseModel):
    items: list[RunResponse]
