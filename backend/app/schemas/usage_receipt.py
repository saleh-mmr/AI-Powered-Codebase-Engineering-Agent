from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: Literal["generation", "query_embedding"]
    model: str
    input_rate: Decimal
    output_rate: Decimal
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: Decimal | None
    started_at: datetime
    finished_at: datetime | None


class RunUsage(BaseModel):
    tracked: bool
    items: list[ReceiptResponse]
    known_cost_usd: Decimal
    unknown_calls: int
