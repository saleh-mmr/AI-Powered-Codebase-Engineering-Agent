from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.generation.contracts import Claim
from app.retrieval.text import query_terms
from app.schemas.search import Evidence


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=512)
    mode: Literal["keyword", "hybrid"] = "keyword"

    @field_validator("question")
    @classmethod
    def meaningful_question(cls, value: str) -> str:
        if not query_terms(value):
            raise ValueError("Question must contain searchable words")
        return value.strip()


class AnswerSettings(BaseModel):
    enabled: bool
    embeddings_enabled: bool
    model: str
    max_output_tokens: int
    input_price_per_million: float
    output_price_per_million: float


class AnswerResponse(BaseModel):
    answer_id: UUID
    status: Literal["answered", "insufficient_evidence", "refused"]
    claims: list[Claim]
    limitation: str
    evidence: list[Evidence]
    source_index_id: UUID
    search_index_id: UUID
    commit_sha: str
    retrieval_mode: Literal["keyword", "hybrid"]
    retrieval_version: str
    embedding_profile: str
    context_tokens: int
    context_omitted: int
    prompt_version: str
    prompt_hash: str
    model: str | None
    input_tokens: int
    output_tokens: int
    estimated_generation_cost_usd: float
    estimated_retrieval_cost_usd: float
    duration_ms: float
    history_turn_ids: list[UUID] = Field(default_factory=list, max_length=3)
    history_tokens: int = Field(default=0, ge=0, le=1000)
    history_policy: str = "none"
