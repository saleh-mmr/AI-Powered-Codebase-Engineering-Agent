import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_required_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="database_url"):
        Settings()


def test_secrets_are_hidden() -> None:
    settings = Settings(database_url="postgresql+asyncpg://user:supersecret@localhost/db")
    assert "supersecret" not in repr(settings)


@pytest.mark.parametrize("url", ["sqlite:///local.db", "postgresql://user:secret@localhost/db"])
def test_unsupported_driver(url: str) -> None:
    with pytest.raises(ValidationError) as error:
        Settings(database_url=url)
    assert url not in str(error.value)
