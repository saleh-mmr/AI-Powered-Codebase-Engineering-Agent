import math
from dataclasses import dataclass
from typing import Protocol

from app.core.errors import AppError

MODEL = "text-embedding-3-small"
DIMENSIONS = 1536
PROFILE = "openai:text-embedding-3-small:1536:cl100k_base:mean-v1"


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    input_tokens: int


class EmbeddingProvider(Protocol):
    profile: str

    def tokenize(self, text: str) -> list[list[int]]: ...

    async def embed(self, inputs: list[list[int]]) -> EmbeddingBatch: ...


def normalize(vector: list[float]) -> list[float]:
    if len(vector) != DIMENSIONS or not all(math.isfinite(v) for v in vector):
        raise AppError(
            "embedding_invalid", "Embedding response has invalid dimensions or values.", 502
        )
    norm = math.sqrt(sum(v * v for v in vector))
    if not math.isfinite(norm) or norm <= 0:
        raise AppError("embedding_invalid", "Embedding response has invalid magnitude.", 502)
    return [v / norm for v in vector]


def aggregate(vectors: list[list[float]], lengths: list[int]) -> list[float]:
    if not vectors or len(vectors) != len(lengths) or any(n <= 0 for n in lengths):
        raise ValueError("Embedding part lengths do not match vectors")
    valid = [normalize(v) for v in vectors]
    total = sum(lengths)
    return normalize(
        [
            sum(v[i] * n / total for v, n in zip(valid, lengths, strict=True))
            for i in range(DIMENSIONS)
        ]
    )
