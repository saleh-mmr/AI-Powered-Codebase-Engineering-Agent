from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.integrations.github.urls import parse_repository_url


class RepositoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(max_length=300)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        owner, name = parse_repository_url(value)
        return f"https://github.com/{owner}/{name}"


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    stage: str
    attempts: int
    files_scanned: int
    files_stored: int
    files_skipped: int
    error_code: str | None
    error_message: str | None


class RepositoryResponse(BaseModel):
    id: UUID
    owner: str
    name: str
    url: str
    github_repository_id: int | None
    default_branch: str | None
    last_commit_sha: str | None
    imported_at: datetime | None
    job: JobResponse


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    path: str
    language: str
    size: int


class FileContentResponse(FileResponse):
    content: str
    commit_sha: str


class FilePage(BaseModel):
    items: list[FileResponse]
    next_offset: int | None
