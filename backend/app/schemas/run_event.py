from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RunEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    run_id: UUID
    sequence: int = Field(ge=1, le=3)
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    occurred_at: datetime
