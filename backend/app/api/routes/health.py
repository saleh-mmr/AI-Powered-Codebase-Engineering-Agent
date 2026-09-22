import logging
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.database.session import ReadinessProbe
from app.schemas.health import ErrorDetail, ErrorResponse, HealthResponse

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger("repopilot.health")


def get_readiness_probe(request: Request) -> ReadinessProbe:
    return cast(ReadinessProbe, request.app.state.readiness_probe)


@router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse()


@router.get("/ready", response_model=HealthResponse, responses={503: {"model": ErrorResponse}})
async def readiness(
    request: Request, probe: Annotated[ReadinessProbe, Depends(get_readiness_probe)]
) -> HealthResponse | JSONResponse:
    try:
        await probe.check()
    except Exception as exc:
        # Health checks deliberately convert dependency failures into a safe 503.
        logger.warning(
            "readiness_failed",
            extra={"error_type": type(exc).__name__, "request_id": request.state.request_id},
        )
        body = ErrorResponse(
            error=ErrorDetail(
                code="dependency_unavailable",
                message="Database not ready. Check connectivity and migrations.",
                request_id=request.state.request_id,
            )
        )
        return JSONResponse(status_code=503, content=body.model_dump())
    return HealthResponse()
