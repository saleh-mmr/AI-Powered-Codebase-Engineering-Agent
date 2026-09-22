import hashlib
import hmac
import re
import secrets

_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")


def new_token() -> str:
    return secrets.token_urlsafe(32)


def valid_token(token: str | None) -> bool:
    return token is not None and _PATTERN.fullmatch(token) is not None


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(token: str) -> str:
    # Domain separation: this proof cannot be used as the authentication cookie.
    return hmac.new(token.encode(), b"repopilot:csrf:v1", hashlib.sha256).hexdigest()
