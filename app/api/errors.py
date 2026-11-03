from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AppError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    TooManyRequestsError,
)

_STATUS_CODES: dict[type[AppError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
    TooManyRequestsError: status.HTTP_429_TOO_MANY_REQUESTS,
}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    status_code = next(
        (code for error_type, code in _STATUS_CODES.items() if isinstance(exc, error_type)),
        status.HTTP_400_BAD_REQUEST,
    )
    headers: dict[str, str] = {}
    if isinstance(exc, AuthenticationError):
        headers["WWW-Authenticate"] = "Bearer"
    if isinstance(exc, TooManyRequestsError):
        headers["Retry-After"] = str(exc.retry_after)

    # Same shape as FastAPI's own HTTPException responses.
    return JSONResponse({"detail": exc.message}, status_code=status_code, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
