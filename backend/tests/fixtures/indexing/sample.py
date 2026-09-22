"""Small indexing fixture. Its source is parsed, never imported."""

from pathlib import Path as FilePath  # noqa: F401

DEFAULT_LIMIT = 3


class Catalog:
    label = "books"

    @staticmethod
    def find(name: str) -> str:
        """Return a matching name."""

        def normalize(value: str) -> str:
            return value.lower()

        return normalize(name)


async def refresh() -> None:
    raise RuntimeError("Do not execute indexing fixtures")
