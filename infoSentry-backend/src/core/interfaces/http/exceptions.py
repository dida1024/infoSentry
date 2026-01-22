"""HTTP exception handlers."""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from src.core.domain.exceptions import (
    AuthorizationError,
    BudgetExceededError,
    DomainException,
    DuplicateEntityError,
    EntityNotFoundError,
    ValidationError,
)
from src.modules.users.domain.exceptions import (
    DeviceSessionExpiredError,
    DeviceSessionNotFoundError,
    DeviceSessionRevokedError,
    DeviceSessionRiskBlockedError,
    InvalidMagicLinkError,
    MagicLinkAlreadyUsedError,
    MagicLinkExpiredError,
    RefreshTokenMissingError,
)


class BizException(Exception):
    """Business logic exception."""

    def __init__(
        self,
        message: str = "业务逻辑错误",
        code: int = 400,
        error_code: str = "BIZ_ERROR",
    ):
        self.message = message
        self.code = code
        self.error_code = error_code
        super().__init__(message)


async def biz_exception_handler(_request: Request, exc: BizException) -> JSONResponse:
    """Handle business exceptions."""
    return JSONResponse(
        status_code=exc.code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
            }
        },
    )


async def domain_exception_handler(
    _request: Request, exc: DomainException
) -> JSONResponse:
    """Handle domain exceptions."""
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "DOMAIN_ERROR"

    if isinstance(exc, EntityNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
        error_code = "NOT_FOUND"
    elif isinstance(exc, DuplicateEntityError):
        status_code = status.HTTP_409_CONFLICT
        error_code = "DUPLICATE_ENTITY"
    elif isinstance(exc, ValidationError):
        status_code = status.HTTP_400_BAD_REQUEST
        error_code = "VALIDATION_ERROR"
    elif isinstance(exc, AuthorizationError):
        status_code = status.HTTP_403_FORBIDDEN
        error_code = "FORBIDDEN"
    elif isinstance(exc, BudgetExceededError):
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
        error_code = "BUDGET_EXCEEDED"
    elif isinstance(exc, InvalidMagicLinkError):
        status_code = status.HTTP_400_BAD_REQUEST
        error_code = "INVALID_MAGIC_LINK"
    elif isinstance(exc, MagicLinkAlreadyUsedError):
        status_code = status.HTTP_400_BAD_REQUEST
        error_code = "MAGIC_LINK_ALREADY_USED"
    elif isinstance(exc, MagicLinkExpiredError):
        status_code = status.HTTP_400_BAD_REQUEST
        error_code = "MAGIC_LINK_EXPIRED"
    elif isinstance(exc, RefreshTokenMissingError):
        status_code = status.HTTP_401_UNAUTHORIZED
        error_code = "REFRESH_TOKEN_MISSING"
    elif isinstance(exc, DeviceSessionNotFoundError):
        status_code = status.HTTP_401_UNAUTHORIZED
        error_code = "DEVICE_SESSION_NOT_FOUND"
    elif isinstance(exc, DeviceSessionExpiredError):
        status_code = status.HTTP_401_UNAUTHORIZED
        error_code = "DEVICE_SESSION_EXPIRED"
    elif isinstance(exc, DeviceSessionRevokedError):
        status_code = status.HTTP_401_UNAUTHORIZED
        error_code = "DEVICE_SESSION_REVOKED"
    elif isinstance(exc, DeviceSessionRiskBlockedError):
        status_code = status.HTTP_401_UNAUTHORIZED
        error_code = "DEVICE_SESSION_RISK"

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": error_code,
                "message": exc.message,
            }
        },
    )


async def global_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
            }
        },
    )
