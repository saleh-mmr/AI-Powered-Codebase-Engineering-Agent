import asyncio
import json

import httpx
import pytest

from app.indexing.errors import ImportFailure
from app.integrations.github.client import GitHubClient
from app.integrations.github.urls import parse_repository_url


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a/b",
        "https://github.com:443/a/b",
        "https://github.com.evil/a/b",
        "https://user@github.com/a/b",
        "https://github.com/a/b/tree/main",
        "https://github.com/a/b?x=1",
        "file:///etc/passwd",
        "https://github.com/a/%2e%2e",
    ],
)
def test_url_rejection(url: str) -> None:
    with pytest.raises(ValueError):
        parse_repository_url(url)


def test_url_normalization() -> None:
    assert parse_repository_url("https://github.com/Owner/Repo.git/") == ("owner", "repo")


class Stream(httpx.AsyncByteStream):
    def __init__(self, content: bytes):
        self.content = content

    async def __aiter__(self):
        yield self.content


def response(body: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, stream=Stream(json.dumps(body).encode()))


def test_resolves_default_branch_and_pins_download() -> None:
    paths: list[str] = []
    sha = "a" * 40

    async def scenario() -> None:
        def handle(request: httpx.Request) -> httpx.Response:
            paths.append(str(request.url))
            if request.url.host == "codeload.github.com":
                return httpx.Response(200, stream=Stream(b"archive"))
            if "/commits/" in str(request.url):
                return response({"sha": sha})
            return response(
                {
                    "id": 1,
                    "private": False,
                    "full_name": "owner/repo",
                    "default_branch": "feature/default",
                }
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            client = GitHubClient(http, 1000)
            source = await client.resolve("owner", "repo")
            assert source.branch == "feature/default" and source.sha == sha
            assert await client.download(source) == b"archive"

    asyncio.run(scenario())
    assert paths[1].endswith("feature%2Fdefault")
    assert paths[-1] == f"https://codeload.github.com/owner/repo/tar.gz/{sha}"


@pytest.mark.parametrize(
    "status,code",
    [
        (404, "repository_unavailable"),
        (403, "github_rate_limited"),
        (429, "github_rate_limited"),
        (302, "repository_moved"),
        (503, "github_unavailable"),
    ],
)
def test_external_errors(status: int, code: str) -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: response({}, status))
        ) as http:
            with pytest.raises(ImportFailure) as exc:
                await GitHubClient(http, 1000).resolve("owner", "repo")
            assert exc.value.code == code

    asyncio.run(scenario())


def test_metadata_and_download_limits() -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, stream=Stream(b"x" * 200))
            )
        ) as http:
            with pytest.raises(ImportFailure, match="size limit"):
                await GitHubClient(http, 100)._get(
                    "https://codeload.github.com/o/r/tar.gz/sha", 100
                )
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: response(
                    {"id": 1, "private": True, "full_name": "o/r", "default_branch": "main"}
                )
            )
        ) as http:
            with pytest.raises(ImportFailure, match="Only public"):
                await GitHubClient(http, 100).resolve("o", "r")

    asyncio.run(scenario())
