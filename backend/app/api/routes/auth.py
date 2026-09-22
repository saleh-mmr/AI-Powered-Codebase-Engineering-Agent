from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies.auth import (
    SESSION_COOKIE,
    check_auth_throttle,
    current_identity,
    get_service,
    get_settings,
    require_browser_request,
    require_csrf,
)
from app.auth.tokens import csrf_token
from app.core.config import Settings
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.schemas.health import ErrorResponse
from app.services.auth import AuthService, Identity

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)


def auth_response(identity: Identity) -> AuthResponse:
    return AuthResponse(
        user=UserResponse.model_validate(identity.user),
        csrf_token=csrf_token(identity.token),
        expires_at=identity.session.expires_at,
    )


def set_session_cookie(response: Response, identity: Identity, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        identity.token,
        max_age=settings.session_lifetime_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post(
    "/register",
    status_code=201,
    response_model=AuthResponse,
    dependencies=[Depends(require_browser_request)],
    responses={409: {"model": ErrorResponse}},
)
async def register(
    data: RegisterRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthResponse:
    check_auth_throttle(request, str(data.email))
    identity = await service.register(data, request.cookies.get(SESSION_COOKIE))
    set_session_cookie(response, identity, settings)
    return auth_response(identity)


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(require_browser_request)])
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthResponse:
    check_auth_throttle(request, str(data.email))
    identity = await service.login(data, request.cookies.get(SESSION_COOKIE))
    set_session_cookie(response, identity, settings)
    return auth_response(identity)


@router.get("/me", response_model=AuthResponse)
async def me(identity: Annotated[Identity, Depends(current_identity)]) -> AuthResponse:
    return auth_response(identity)


@router.post("/logout", status_code=204, dependencies=[Depends(require_browser_request)])
async def logout(
    identity: Annotated[Identity, Depends(require_csrf)],
    service: Annotated[AuthService, Depends(get_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    await service.logout(identity)
    response = Response(status_code=204)
    response.delete_cookie(
        SESSION_COOKIE, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax"
    )
    return response
