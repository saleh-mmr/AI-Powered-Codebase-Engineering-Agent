import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def error_response(request: Request, code: str, message: str, status: int) -> JSONResponse:
    headers = {"Retry-After": "60"} if status == 429 else None
    return JSONResponse(
        status_code=status,
        headers=headers,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request.state.request_id,
            }
        },
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def application_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(request, exc.code, exc.message, exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Do not echo Pydantic's input values: auth requests contain passwords.
        return error_response(
            request, "validation_error", "Check the submitted fields and try again.", 422
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return error_response(
            request, "request_error", "The request could not be completed.", exc.status_code
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logging.getLogger("repopilot.database").error(
            "database_operation_failed",
            extra={
                "request_id": request.state.request_id,
                "error_type": type(exc).__name__,
            },
        )
        return error_response(
            request,
            "database_unavailable",
            "Database operation failed. Check availability and migrations.",
            503,
        )
