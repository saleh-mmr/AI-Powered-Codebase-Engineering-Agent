from pydantic import Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore", hide_input_in_errors=True)

    database_url: SecretStr
    database_timeout_seconds: float = Field(default=3.0, ge=0.1, le=30)

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
