from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class SourceChunk:
    id: UUID
    file_id: UUID
    path: str
    language: str
    name: str | None
    signature: str | None
    content: str
    start_line: int
    end_line: int
    start_offset: int
    end_offset: int


class CandidateStore(Protocol):
    async def lexical(self, index_id: UUID, terms: list[str]) -> list[UUID]: ...
    async def symbols(self, index_id: UUID, terms: list[str]) -> list[UUID]: ...
    async def vector(self, index_id: UUID, vector: list[float]) -> list[UUID]: ...
