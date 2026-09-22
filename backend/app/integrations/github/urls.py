import re
from urllib.parse import urlsplit

_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")


def parse_repository_url(value: str) -> tuple[str, str]:
    url = urlsplit(value.strip())
    parts = url.path.strip("/").split("/")
    if (
        url.scheme != "https"
        or url.netloc != "github.com"
        or url.query
        or url.fragment
        or len(parts) != 2
        or any(not _PATTERN.fullmatch(part) or part in {".", ".."} for part in parts)
    ):
        raise ValueError(
            "Use https://github.com/owner/repository without extra path, credentials, or query."
        )
    owner, name = parts
    if name.endswith(".git"):
        name = name[:-4]
    if not name or name in {".", ".."}:
        raise ValueError("Invalid repository name")
    return owner.lower(), name.lower()
