"""Best-effort display projection of partial structured output; never an answer validator."""

from pydantic import TypeAdapter, ValidationError

PARTIAL_OBJECT = TypeAdapter(dict[str, object])
MAX_PREVIEW_CHARS = 8000


def preview_text(raw_json: str) -> str:
    try:
        # Partial parsing is intentionally restricted to the display path.
        data = PARTIAL_OBJECT.validate_json(raw_json, experimental_allow_partial="trailing-strings")
    except ValidationError:
        return ""
    texts: list[str] = []
    claims = data.get("claims")
    if isinstance(claims, list):
        for claim in claims[:8]:
            if isinstance(claim, dict) and isinstance(claim.get("text"), str):
                texts.append(claim["text"][:1800])
    limitation = data.get("limitation")
    if isinstance(limitation, str):
        texts.append(limitation[:1200])
    # PostgreSQL text cannot contain NUL or unpaired Unicode surrogates.
    return (
        "\n\n".join(text for text in texts if text)[:MAX_PREVIEW_CHARS]
        .replace("\x00", "")
        .encode("utf-8", errors="replace")
        .decode()
    )
