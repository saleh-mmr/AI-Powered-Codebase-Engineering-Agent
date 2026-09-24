from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import AppError
from app.generation.contracts import AnswerDraft, GenerationResult


class Content(BaseModel):
    type: str
    text: str | None = None


class OutputItem(BaseModel):
    id: str | None = None
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


def validate_response(value: object, model: str, max_output_tokens: int) -> GenerationResult:
    data = ResponsePayload.model_validate(value)
    if data.status != "completed":
        raise AppError(
            "model_incomplete", "Model output was incomplete. No answer was published.", 502
        )
    if data.model != model:
        raise ValueError("Unexpected model snapshot")
    if data.usage.total_tokens != data.usage.input_tokens + data.usage.output_tokens:
        raise ValueError("Inconsistent usage")
    if data.usage.output_tokens > max_output_tokens:
        raise ValueError("Output token limit exceeded")
    messages = [item for item in data.output if item.type == "message"]
    if len(messages) != 1 or messages[0].role != "assistant" or (messages[0].status != "completed"):
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
