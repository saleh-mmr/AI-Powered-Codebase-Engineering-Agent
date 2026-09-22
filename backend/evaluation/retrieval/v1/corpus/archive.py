from pathlib import PurePosixPath


def validate_archive_path(path: str) -> bool:
    """Reject absolute paths and parent traversal in an untrusted source archive."""
    parts = PurePosixPath(path)
    return not parts.is_absolute() and ".." not in parts.parts


def accept_text_file(size: int, maximum: int = 262144) -> bool:
    """Apply the per-file byte limit before retaining imported source text."""
    return 0 <= size <= maximum
