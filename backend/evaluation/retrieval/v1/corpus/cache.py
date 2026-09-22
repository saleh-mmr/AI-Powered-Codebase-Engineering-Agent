def evict_cache_entry(cache: dict[str, str], key: str) -> None:
    """Remove cached data for one key without changing persistent records."""
    cache.pop(key, None)


def normalize_query(query: str) -> str:
    """Normalize whitespace before logging a query length, never its contents."""
    return " ".join(query.split())
