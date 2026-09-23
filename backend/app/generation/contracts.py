from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1, max_length=1800)
    citation_ids: list[str] = Field(min_length=1, max_length=8)


class AnswerDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["answered", "insufficient_evidence"]
    claims: list[Claim] = Field(max_length=8)
    limitation: str = Field(max_length=1200)

    @model_validator(mode="after")
    def check_status(self) -> "AnswerDraft":
        if (self.status == "answered") != bool(self.claims):
            raise ValueError("Answered requires claims; abstention must not contain claims")
        if self.status == "insufficient_evidence" and not self.limitation.strip():
            raise ValueError("Abstention requires an explanation")
        if any(not c.text.strip() for c in self.claims):
            raise ValueError("Claims cannot be blank")
        return self


class GenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    model: str = Field(min_length=1, max_length=100)
    draft: AnswerDraft | None
    refused: bool
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def check_result(self) -> "GenerationResult":
        if self.refused != (self.draft is None):
            raise ValueError("Refused results have no answer draft")
        return self


class AnswerProvider(Protocol):
    @property
    def model(self) -> str: ...

    async def generate(self, instructions: str, evidence_input: str) -> GenerationResult: ...
