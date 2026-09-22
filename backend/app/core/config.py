from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore", hide_input_in_errors=True)

    database_url: SecretStr
    database_timeout_seconds: float = Field(default=3.0, ge=0.1, le=30)

    environment: Literal["development", "production", "test"] = "development"
    frontend_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    session_lifetime_hours: int = Field(default=24, ge=1, le=168)

    @field_validator("frontend_origin")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
        ):
            raise ValueError("must be an HTTP(S) origin without path or credentials")
        return value

    @model_validator(mode="after")
    def production_cookies(self) -> "Settings":
        if self.environment == "production" and (
            not self.cookie_secure or not self.frontend_origin.startswith("https://")
        ):
            raise ValueError("production requires HTTPS frontend origin and secure cookies")
        return self

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        try:
            parsed = PostgresDsn(raw)
        except ValueError:
            raise ValueError("must be a valid PostgreSQL connection URL") from None
        if parsed.scheme != "postgresql+asyncpg":
            raise ValueError("must use the postgresql+asyncpg driver")
        if not parsed.path or parsed.path == "/":
            raise ValueError("must include a database name")
        return value
