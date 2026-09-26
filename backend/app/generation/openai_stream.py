"""Bounded Responses SSE adapter; never forwards reasoning or tool events."""

import codecs
import json
from collections.abc import AsyncIterator

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import AppError
from app.core.provider_usage import ProviderUsageError
from app.generation.contracts import DeltaSink, GenerationResult
from app.generation.openai_payload import ResponsePayload, validate_response


class Envelope(BaseModel):
    model_config = ConfigDict(strict=True)
    type: str
    sequence_number: int = Field(ge=0)


class TextDelta(Envelope):
    item_id: str
    output_index: int = Field(ge=0)
    content_index: int = Field(ge=0)
    delta: str


async def frames(response: httpx.Response) -> AsyncIterator[dict[str, object]]:
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    buffer = ""
    total = 0
    async for block in response.aiter_bytes():
        total += len(block)
        if total > 2 * 1024 * 1024:
            raise ValueError("Provider stream exceeds byte budget")
        buffer += decoder.decode(block)
        buffer = buffer.replace("\r\n", "\n")
        while "\n\n" in buffer:
            frame, buffer = buffer.split("\n\n", 1)
            if len(frame.encode()) > 256 * 1024:
                raise ValueError("Provider event exceeds byte budget")
            data = "\n".join(
                line[5:].removeprefix(" ") for line in frame.split("\n") if line.startswith("data:")
            )
            if data:
                parsed = json.loads(data)
                if not isinstance(parsed, dict):
                    raise ValueError("Expected event object")
                yield parsed
        if len(buffer.encode()) > 256 * 1024:
            raise ValueError("Provider event exceeds byte budget")
    # Completion must have arrived as a framed event, not EOF/unterminated JSON.
    raise AppError("model_incomplete", "Model stream ended before completion.", 502)


async def consume_stream(
    response: httpx.Response, model: str, output_cap: int, on_delta: DeltaSink
) -> GenerationResult:
    sequence = -1
    identity: tuple[str, int, int] | None = None
    accumulated = ""
    count = 0
    async for value in frames(response):
        count += 1
        if count > 12000:
            raise ValueError("Too many provider events")
        if value.get("type") in {
            "error",
            "response.error",
            "response.failed",
            "response.incomplete",
        }:
            if value.get("response") is not None:
                validate_response(value.get("response"), model, output_cap)
            raise AppError("model_incomplete", "Model stream did not complete successfully.", 502)
        event = Envelope.model_validate(value)
        if event.sequence_number <= sequence:
            raise ValueError("Out-of-order provider event")
        sequence = event.sequence_number
        if event.type == "response.output_text.delta":
            delta = TextDelta.model_validate(value)
            current = (delta.item_id, delta.output_index, delta.content_index)
            if identity is not None and current != identity:
                raise ValueError("Multiple output streams are not supported")
            identity = current
            accumulated += delta.delta
            if len(accumulated.encode()) > 64 * 1024:
                raise ValueError("Model text exceeds limit")
            await on_delta(delta.delta)
        elif event.type == "response.completed":
            result = validate_response(value.get("response"), model, output_cap)
            payload = ResponsePayload.model_validate(value.get("response"))
            try:
                if not result.refused:
                    if identity is None:
                        raise ValueError("Missing text deltas")
                    item_id, output_index, content_index = identity
                    if output_index >= len(payload.output):
                        raise ValueError("Invalid output index")
                    item = payload.output[output_index]
                    if item.id != item_id or content_index >= len(item.content):
                        raise ValueError("Invalid output identity")
                    if item.content[content_index].text != accumulated:
                        raise ValueError("Completed text differs from streamed text")
            except ValueError:
                raise ProviderUsageError(
                    AppError("model_invalid", "Model output failed validation.", 502),
                    result.input_tokens,
                    result.output_tokens,
                ) from None
            return result
        # Lifecycle/refusal metadata is not rendered. No reasoning/tool contents leave this adapter.
    raise AppError("model_incomplete", "Model stream ended before completion.", 502)
