import hmac
from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.throttle import AuthThrottle
from app.auth.tokens import csrf_token
from app.core.config import Settings
from app.core.errors import AppError
from app.services.auth import AuthService, Identity

SESSION_COOKIE = "repopilot_session"


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    factory = cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)
    async with factory() as db:
        yield db


def get_service(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(db, settings.session_lifetime_hours, request.app.state.dummy_password_hash)


async def current_identity(
    request: Request,
    service: Annotated[AuthService, Depends(get_service)],
) -> Identity:
    return await service.authenticate(request.cookies.get(SESSION_COOKIE))


def require_browser_request(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if (
        request.headers.get("origin") != settings.frontend_origin
        or request.headers.get("x-repopilot-request") != "1"
    ):
        raise AppError(
            "csrf_failed", "Request origin could not be verified. Reload and try again.", 403
        )
    if (
        request.method in {"POST", "PUT", "PATCH"}
        and request.headers.get("content-type", "").split(";")[0] != "application/json"
    ):
        raise AppError("unsupported_media_type", "Use application/json.", 415)


def require_csrf(
    request: Request,
    identity: Annotated[Identity, Depends(current_identity)],
    _: Annotated[None, Depends(require_browser_request)],
) -> Identity:
    supplied = request.headers.get("x-csrf-token", "")
    # Restrict before compare_digest, which requires ASCII strings.
    if (
        len(supplied) != 64
        or not supplied.isascii()
        or not hmac.compare_digest(supplied, csrf_token(identity.token))
    ):
        raise AppError("csrf_failed", "Session verification failed. Reload and try again.", 403)
    return identity


def check_auth_throttle(request: Request, email: str) -> None:
    limiter = cast(AuthThrottle, request.app.state.auth_throttle)
    peer = request.client.host if request.client else "unknown"
    limiter.check(email, peer)
