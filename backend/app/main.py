import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from app.api.routes.health import router
from app.core.config import Settings
from app.core.logging import configure_logging
from app.database.session import DatabaseProbe, create_engine

logger = logging.getLogger("repopilot.http")


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(config)
        app.state.readiness_probe = DatabaseProbe(engine, config.database_timeout_seconds)
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="RepoPilot AI", version="0.1.0", lifespan=lifespan)
    app.include_router(router)

    @app.middleware("http")
    async def request_logging(request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = perf_counter()
        request_id = str(uuid4())
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "error_type": type(exc).__name__,
                },
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internal_error",
                        "message": "An unexpected error occurred.",
                        "request_id": request_id,
                    }
                },
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        route = request.scope.get("route")
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "route": getattr(route, "path", "unmatched"),
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return response

    return app
