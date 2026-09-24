from uuid import UUID

from pydantic import BaseModel, Field


class AnswerPreview(BaseModel):
    run_id: UUID
    revision: int = Field(ge=0, le=256)
    text: str = Field(max_length=8000)
