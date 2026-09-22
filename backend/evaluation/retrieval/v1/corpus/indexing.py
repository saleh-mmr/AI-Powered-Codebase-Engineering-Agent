import hashlib


def source_fingerprint(content: str) -> str:
    """Compute a stable SHA-256 content hash used to detect changed source chunks."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def lexical_terms(identifier: str) -> list[str]:
    """Split snake_case identifiers into words for keyword retrieval."""
    return identifier.lower().split("_")
