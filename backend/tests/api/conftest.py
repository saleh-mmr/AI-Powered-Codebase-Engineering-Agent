import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import models  # noqa: F401
from app.api.dependencies.auth import get_db
from app.auth.throttle import AuthThrottle
from app.core.config import Settings
from app.core.rate_limits import MemoryRateLimiter
from app.database.base import Base
from app.main import create_app


@pytest.fixture
def auth_client(tmp_path: Path) -> Iterator[TestClient]:
    # This portable test DB is not a substitute for the migrated PostgreSQL CI tests.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}", poolclass=NullPool)

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection: object, record: object) -> None:
        connection.execute("PRAGMA foreign_keys=ON")  # type: ignore[attr-defined]

    async def setup() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(setup())
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def database() -> AsyncIterator[AsyncSession]:
        async with factory() as db:
            yield db

    app = create_app(Settings(database_url="postgresql+asyncpg://user:secret@localhost/db"))
    app.dependency_overrides[get_db] = database
    app.state.test_factory = factory
    with TestClient(app, base_url="http://localhost:3000") as client:
        app.state.rate_limiter = MemoryRateLimiter()
        app.state.auth_throttle = AuthThrottle(app.state.rate_limiter)
        yield client
    asyncio.run(engine.dispose())
