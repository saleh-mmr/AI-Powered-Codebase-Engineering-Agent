import asyncio

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings

settings = Settings()


def migrate(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(settings.database_url.get_secret_value(), poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(url=settings.database_url.get_secret_value(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_online())
