import asyncio
import logging
from uuid import UUID

import httpx
from celery import Celery
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.core.logging import configure_logging
from app.database.session import create_engine
from app.integrations.github.client import GitHubClient
from app.jobs.import_repository import run_import

settings = Settings()
celery_app = Celery("repopilot", broker=settings.redis_url.get_secret_value())
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=150,
    task_time_limit=170,
    broker_transport_options={
        "visibility_timeout": 240,
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
    },
    broker_connection_timeout=2,
    broker_connection_retry_on_startup=True,
    task_publish_retry=False,
    worker_hijack_root_logger=False,
)


async def execute(job_id: UUID) -> None:
    engine = create_engine(settings)
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            await run_import(
                async_sessionmaker(engine, expire_on_commit=False),
                GitHubClient(client, settings.import_download_bytes),
                job_id,
                settings.import_timeout_seconds,
            )
    finally:
        await engine.dispose()


@celery_app.task(name="repopilot.import_repository")  # type: ignore[untyped-decorator]
def import_repository(job_id: str) -> None:
    configure_logging()
    try:
        asyncio.run(execute(UUID(job_id)))
    except Exception as exc:
        # Leave durable queued/leased state for dispatcher recovery, without logging payloads.
        logging.getLogger("repopilot.worker").error(
            "worker_task_failed", extra={"error_type": type(exc).__name__}
        )
