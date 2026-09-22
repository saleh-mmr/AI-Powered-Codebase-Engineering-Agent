from uuid import UUID

from app.retrieval.contracts import CandidateStore


class RecordingCandidates:
    def __init__(self, delegate: CandidateStore) -> None:
        self.delegate = delegate
        self.channels: dict[str, list[UUID]] = {}

    async def lexical(self, index_id: UUID, terms: list[str]) -> list[UUID]:
        result = await self.delegate.lexical(index_id, terms)
        self.channels["lexical"] = result
        return result

    async def symbols(self, index_id: UUID, terms: list[str]) -> list[UUID]:
        result = await self.delegate.symbols(index_id, terms)
        self.channels["symbol"] = result
        return result

    async def vector(self, index_id: UUID, vector: list[float]) -> list[UUID]:
        result = await self.delegate.vector(index_id, vector)
        self.channels["vector"] = result
        return result
