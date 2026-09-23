"""Bounded dialogue data; prior answers are never source evidence."""

import json
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.embeddings.tokens import count_tokens

HISTORY_POLICY = "recent-pairs-v1"
MAX_TURNS = 3
MAX_HISTORY_TOKENS = 1000
MAX_HISTORY_BYTES = 8192


class HistoryTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    turn_id: UUID
    question: str = Field(min_length=1, max_length=512)
    answer: str = Field(min_length=1, max_length=8000)


def history_json(turns: list[HistoryTurn]) -> str:
    return json.dumps([turn.model_dump(mode="json") for turn in turns], ensure_ascii=False)


def history_tokens(turns: list[HistoryTurn]) -> int:
    return count_tokens(history_json(turns)) if turns else 0


def bounded_history(turns: list[HistoryTurn]) -> list[HistoryTurn]:
    """Keep complete most-recent pairs. Never cut a statement mid-sentence."""
    selected = list(turns[-MAX_TURNS:])
    while selected and (
        history_tokens(selected) > MAX_HISTORY_TOKENS
        or len(history_json(selected).encode()) > MAX_HISTORY_BYTES
    ):
        selected.pop(0)
    return selected


def retrieval_question(question: str, turns: list[HistoryTurn]) -> str:
    # No extra model call. Current question has priority within SearchRequest's limit.
    # Include only user text, never model-generated claims, as the retrieval hint.
    if not turns or len(question) >= 510:
        return question
    return question + "\n" + turns[-1].question[: 511 - len(question)]
