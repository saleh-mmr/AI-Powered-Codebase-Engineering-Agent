import asyncio
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings


class ReadinessProbe(Protocol):
    async def check(self) -> None: ...


class DatabaseProbe:
    def __init__(self, engine: AsyncEngine, timeout_seconds: float) -> None:
        self.engine = engine
        self.timeout_seconds = timeout_seconds

    async def check(self) -> None:
        async with asyncio.timeout(self.timeout_seconds):
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
                enabled = await connection.scalar(
                    text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
                )
                if not enabled:
                    raise RuntimeError("required_extension_missing")


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=settings.database_timeout_seconds,
        connect_args={
            "timeout": settings.database_timeout_seconds,
            "command_timeout": settings.database_timeout_seconds,
        },
        hide_parameters=True,
    )
