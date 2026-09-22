from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["repopilot-api"] = "repopilot-api"


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
