from dataclasses import dataclass
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.indexing.errors import ImportFailure
from app.integrations.github.urls import parse_repository_url


class Metadata(BaseModel):
    model_config = ConfigDict(strict=True)
    id: int = Field(gt=0)
    private: bool
    full_name: str
    default_branch: str = Field(min_length=1, max_length=255)


class Commit(BaseModel):
    sha: str = Field(pattern=r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class RepositorySource:
    github_id: int
    owner: str
    name: str
    branch: str
    sha: str


class GitHubClient:
    def __init__(self, client: httpx.AsyncClient, archive_limit: int) -> None:
        self.client, self.archive_limit = client, archive_limit

    async def _get(self, url: str, limit: int) -> bytes:
        try:
            async with self.client.stream(
                "GET",
                url,
                follow_redirects=False,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "RepoPilot-AI",
                    "X-GitHub-Api-Version": "2026-03-10",
                    "Accept-Encoding": "identity",
                },
            ) as response:
                status = response.status_code
                if status in {403, 429}:
                    raise ImportFailure(
                        "github_rate_limited", "GitHub access was limited. Wait and retry."
                    )
                if status == 404:
                    raise ImportFailure(
                        "repository_unavailable",
                        "Repository or commit is inaccessible, deleted, or not public.",
                    )
                if status in {301, 302, 307, 308}:
                    raise ImportFailure(
                        "repository_moved",
                        "GitHub redirected this request. Use the repository's current URL.",
                    )
                if status >= 500:
                    raise ImportFailure(
                        "github_unavailable", "GitHub is temporarily unavailable.", True
                    )
                if status != 200:
                    raise ImportFailure(
                        "github_error", "GitHub could not provide this repository or commit."
                    )
                # Prevent transparent decompression from bypassing the byte cap.
                if response.headers.get("content-encoding", "identity") != "identity":
                    raise ImportFailure(
                        "unexpected_encoding", "GitHub returned an unsupported transport encoding."
                    )
                content = bytearray()
                async for chunk in response.aiter_raw():
                    if len(content) + len(chunk) > limit:
                        raise ImportFailure(
                            "repository_too_large",
                            "Repository download exceeds the configured size limit.",
                        )
                    content.extend(chunk)
                return bytes(content)
        except httpx.HTTPError as exc:
            raise ImportFailure(
                "github_network_error", "GitHub request failed or timed out.", True
            ) from exc

    async def resolve(self, owner: str, name: str) -> RepositorySource:
        try:
            meta = Metadata.model_validate_json(
                await self._get(f"https://api.github.com/repos/{owner}/{name}", 1024 * 1024)
            )
            if meta.private:
                raise ImportFailure("private_repository", "Only public repositories are supported.")
            canonical_owner, canonical_name = parse_repository_url(
                "https://github.com/" + meta.full_name
            )
            commit = Commit.model_validate_json(
                await self._get(
                    f"https://api.github.com/repos/{canonical_owner}/{canonical_name}/commits/"
                    f"{quote(meta.default_branch, safe='')}",
                    4 * 1024 * 1024,
                )
            )
            return RepositorySource(
                meta.id, canonical_owner, canonical_name, meta.default_branch, commit.sha
            )
        except (ValidationError, ValueError) as exc:
            raise ImportFailure(
                "github_invalid_response", "GitHub returned unexpected repository metadata."
            ) from exc

    async def download(self, source: RepositorySource) -> bytes:
        return await self._get(
            f"https://codeload.github.com/{source.owner}/{source.name}/tar.gz/{source.sha}",
            self.archive_limit,
        )
