import pytest
from pydantic import ValidationError

from app.auth.tokens import csrf_token, new_token, token_hash, valid_token
from app.core.config import Settings

URL = "postgresql+asyncpg://user:secret@localhost/db"


def test_token_and_csrf_are_distinct() -> None:
    token = new_token()
    assert valid_token(token)
    assert token != csrf_token(token) != token_hash(token)
    assert csrf_token(token) == csrf_token(token)
    assert not valid_token(csrf_token(token))


def test_production_requires_https_and_secure_cookies() -> None:
    with pytest.raises(ValidationError, match="production requires"):
        Settings(database_url=URL, environment="production")
    Settings(
        database_url=URL,
        environment="production",
        cookie_secure=True,
        frontend_origin="https://repopilot.example",
    )


@pytest.mark.parametrize(
    "origin", ["http://localhost:3000/", "https://user:pass@example.com", "null", "file:///tmp"]
)
def test_origin_is_exact(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=URL, frontend_origin=origin)
