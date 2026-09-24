import json

import httpx
from pydantic import ValidationError

from app.core.errors import AppError
from app.generation.contracts import AnswerDraft, DeltaSink, GenerationResult
from app.generation.openai_payload import validate_response
from app.generation.openai_stream import consume_stream


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
                json=self.request_body(instructions, evidence_input),
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
            return validate_response(json.loads(body), self.model, self.max_output_tokens)
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

    def request_body(self, instructions: str, evidence_input: str) -> dict[str, object]:
        return {
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
        }

    async def generate_stream(
        self, instructions: str, evidence_input: str, on_delta: DeltaSink
    ) -> GenerationResult:
        try:
            async with self.client.stream(
                "POST",
                "https://api.openai.com/v1/responses",
                headers={"Authorization": "Bearer " + self.key},
                json={**self.request_body(instructions, evidence_input), "stream": True},
                timeout=30,
                follow_redirects=False,
            ) as response:
                if response.status_code == 429:
                    raise AppError(
                        "model_rate_limited", "Model provider is busy. Retry later.", 503
                    )
                if response.status_code != 200:
                    raise AppError("model_provider_error", "Model streaming request failed.", 502)
                if not response.headers.get("content-type", "").startswith("text/event-stream"):
                    raise ValueError("Expected provider event stream")
                return await consume_stream(response, self.model, self.max_output_tokens, on_delta)
        except (httpx.HTTPError, TimeoutError):
            raise AppError(
                "model_unavailable",
                "Model stream was interrupted. No automatic retry was made.",
                503,
            ) from None
        except (ValidationError, ValueError, TypeError, UnicodeError):
            raise AppError(
                "model_invalid", "Model stream failed validation. No answer was published.", 502
            ) from None
