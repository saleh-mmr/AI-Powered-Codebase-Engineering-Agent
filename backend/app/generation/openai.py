import json

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.errors import AppError
from app.generation.contracts import AnswerDraft, GenerationResult


class Content(BaseModel):
    type: str
    text: str | None = None


class OutputItem(BaseModel):
    type: str
    role: str | None = None
    status: str | None = None
    content: list[Content] = Field(default_factory=list)


class Usage(BaseModel):
    model_config = ConfigDict(strict=True)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class ResponsePayload(BaseModel):
    status: str
    model: str
    output: list[OutputItem]
    usage: Usage


class OpenAIAnswers:
    def __init__(
        self, client: httpx.AsyncClient, key: str, model: str, max_output_tokens: int
    ) -> None:
        self.client, self.key, self.model = client, key, model
        self.max_output_tokens = max_output_tokens

    async def generate(self, instructions: str, evidence_input: str) -> GenerationResult:
        try:
            # No retries: an ambiguous timeout may already have incurred provider charges.
            async with self.client.stream(
                "POST",
                "https://api.openai.com/v1/responses",
                headers={"Authorization": "Bearer " + self.key},
                json={
                    "model": self.model,
                    "instructions": instructions,
                    "input": [{"role": "user", "content": evidence_input}],
                    "store": False,
                    "tools": [],
                    "max_output_tokens": self.max_output_tokens,
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "repository_answer",
                            "strict": True,
                            "schema": AnswerDraft.model_json_schema(),
                        }
                    },
                },
                timeout=30,
                follow_redirects=False,
            ) as response:
                if response.status_code == 429:
                    raise AppError(
                        "model_rate_limited", "Model provider is busy. Retry later.", 503
                    )
                if response.status_code != 200:
                    raise AppError(
                        "model_provider_error",
                        "Model request failed. Check provider configuration and availability.",
                        502,
                    )
                body = bytearray()
                async for block in response.aiter_bytes():
                    body.extend(block)
                    if len(body) > 256 * 1024:
                        raise ValueError("Oversized model response")
            data = ResponsePayload.model_validate(json.loads(body))
            if data.status != "completed":
                raise AppError(
                    "model_incomplete", "Model output was incomplete. No answer was published.", 502
                )
            if data.model != self.model:
                raise ValueError("Unexpected model snapshot")
            if data.usage.total_tokens != data.usage.input_tokens + data.usage.output_tokens:
                raise ValueError("Inconsistent usage")
            if data.usage.output_tokens > self.max_output_tokens:
                raise ValueError("Output token limit exceeded")
            messages = [item for item in data.output if item.type == "message"]
            if (
                len(messages) != 1
                or messages[0].role != "assistant"
                or (messages[0].status != "completed")
            ):
                raise ValueError("Expected one completed assistant message")
            content = messages[0].content
            if len(content) != 1 or content[0].type not in {"output_text", "refusal"}:
                raise ValueError("Unexpected output content")
            refused = content[0].type == "refusal"
            draft = None if refused else AnswerDraft.model_validate_json(content[0].text or "")
            return GenerationResult(
                model=data.model,
                draft=draft,
                refused=refused,
                input_tokens=data.usage.input_tokens,
                output_tokens=data.usage.output_tokens,
            )
        except (httpx.HTTPError, TimeoutError):
            raise AppError(
                "model_unavailable", "Model provider timed out or is unavailable. Retry later.", 503
            ) from None
        except (ValidationError, ValueError, TypeError):
            raise AppError(
                "model_invalid",
                "Model provider returned an invalid answer. Nothing was published.",
                502,
            ) from None
