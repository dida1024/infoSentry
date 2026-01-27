"""User domain exceptions.

每个异常类定义自己的 http_status_code 和 error_code，
由 core/interfaces/http/exceptions.py 中的 domain_exception_handler 统一处理。
"""

from fastapi import status

from src.core.domain.exceptions import DomainException, EntityNotFoundError


class UserNotFoundError(EntityNotFoundError):
    """Raised when user is not found."""

    def __init__(self, user_id: str | None = None, email: str | None = None) -> None:
        if email:
            super().__init__("User", email)
        else:
            super().__init__("User", user_id)


class UserAlreadyExistsError(DomainException):
    """Raised when user already exists."""

    http_status_code = status.HTTP_409_CONFLICT
    error_code = "USER_ALREADY_EXISTS"

    def __init__(self, email: str) -> None:
        super().__init__(f"User with email '{email}' already exists")


class MagicLinkExpiredError(DomainException):
    """Raised when magic link has expired."""

    http_status_code = status.HTTP_400_BAD_REQUEST
    error_code = "MAGIC_LINK_EXPIRED"

    def __init__(self) -> None:
        super().__init__("Magic link has expired")


class MagicLinkAlreadyUsedError(DomainException):
    """Raised when magic link has already been used."""

    http_status_code = status.HTTP_400_BAD_REQUEST
    error_code = "MAGIC_LINK_ALREADY_USED"

    def __init__(self) -> None:
        super().__init__("Magic link has already been used")


class InvalidMagicLinkError(DomainException):
    """Raised when magic link is invalid."""

    http_status_code = status.HTTP_400_BAD_REQUEST
    error_code = "INVALID_MAGIC_LINK"

    def __init__(self) -> None:
        super().__init__("Invalid magic link")


class RefreshTokenMissingError(DomainException):
    """Raised when refresh token cookie is missing."""

    http_status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "REFRESH_TOKEN_MISSING"

    def __init__(self) -> None:
        super().__init__("Refresh token is missing")


class DeviceSessionNotFoundError(DomainException):
    """Raised when device session is not found."""

    http_status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "DEVICE_SESSION_NOT_FOUND"

    def __init__(self) -> None:
        super().__init__("Device session not found")


class DeviceSessionExpiredError(DomainException):
    """Raised when device session has expired."""

    http_status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "DEVICE_SESSION_EXPIRED"

    def __init__(self) -> None:
        super().__init__("Device session has expired")


class DeviceSessionRevokedError(DomainException):
    """Raised when device session has been revoked."""

    http_status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "DEVICE_SESSION_REVOKED"

    def __init__(self) -> None:
        super().__init__("Device session has been revoked")


class DeviceSessionRiskBlockedError(DomainException):
    """Raised when device session is blocked by risk checks."""

    http_status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "DEVICE_SESSION_RISK"

    def __init__(self) -> None:
        super().__init__("Device session requires re-authentication")
