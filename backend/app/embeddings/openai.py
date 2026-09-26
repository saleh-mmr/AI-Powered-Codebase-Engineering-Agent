import json

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.errors import AppError
from app.core.provider_usage import ProviderUsageError
from app.embeddings.provider import MODEL, PROFILE, EmbeddingBatch, normalize
from app.embeddings.tokens import token_parts


class VectorItem(BaseModel):
    model_config = ConfigDict(strict=True)
    index: int = Field(ge=0)
    embedding: list[float]


class Usage(BaseModel):
    model_config = ConfigDict(strict=True)
    prompt_tokens: int = Field(ge=0)


class Payload(BaseModel):
    model: str
    data: list[VectorItem]
    usage: Usage


class OpenAIEmbeddings:
    profile = PROFILE

    def __init__(self, client: httpx.AsyncClient, key: str) -> None:
        self.client, self.key = client, key

    def tokenize(self, text: str) -> list[list[int]]:
        return token_parts(text)

    async def embed(self, inputs: list[list[int]]) -> EmbeddingBatch:
        if not inputs or len(inputs) > 64 or any(not x or len(x) > 4096 for x in inputs):
            raise ValueError("Invalid embedding batch")
        if sum(map(len, inputs)) > 250000:
            raise ValueError("Embedding batch token limit exceeded")
        known_tokens: int | None = None
        try:
            async with self.client.stream(
                "POST",
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": "Bearer " + self.key},
                json={
                    "model": MODEL,
                    "input": inputs,
                    "encoding_format": "float",
                    "dimensions": 1536,
                },
                timeout=15,
                follow_redirects=False,
            ) as response:
                if response.status_code == 429:
                    raise AppError(
                        "embedding_rate_limited",
                        "Embedding provider rate limit reached. Retry later.",
                        503,
                    )
                if response.status_code != 200:
                    raise AppError(
                        "embedding_provider_error",
                        "Embedding provider rejected the request. "
                        "Check its configuration and availability.",
                        502,
                    )
                body = bytearray()
                async for block in response.aiter_bytes():
                    body.extend(block)
                    if len(body) > 8 * 1024 * 1024:
                        raise AppError(
                            "embedding_invalid", "Embedding response exceeded its size limit.", 502
                        )
            raw = json.loads(body)
            if isinstance(raw, dict) and raw.get("model") == MODEL:
                usage = Usage.model_validate(raw.get("usage"))
                if usage.prompt_tokens == sum(map(len, inputs)):
                    known_tokens = usage.prompt_tokens
            data = Payload.model_validate(raw)
            if data.model != MODEL or sorted(x.index for x in data.data) != list(
                range(len(inputs))
            ):
                raise ValueError("Mismatched response")
            if data.usage.prompt_tokens != sum(map(len, inputs)):
                raise ValueError("Usage does not match supplied token inputs")
            ordered = sorted(data.data, key=lambda x: x.index)
            return EmbeddingBatch(
                [normalize(x.embedding) for x in ordered], data.usage.prompt_tokens
            )
        except (httpx.HTTPError, TimeoutError):
            raise AppError(
                "embedding_unavailable", "Embedding provider is unavailable. Retry later.", 503
            ) from None
        except (AppError, ValidationError, ValueError, TypeError) as exc:
            error = (
                exc
                if isinstance(exc, AppError)
                else AppError(
                    "embedding_invalid", "Embedding provider returned an invalid response.", 502
                )
            )
            if known_tokens is not None:
                raise ProviderUsageError(error, known_tokens, 0) from None
            raise error from None
