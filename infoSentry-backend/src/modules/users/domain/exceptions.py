"""User domain exceptions."""

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

    def __init__(self, email: str) -> None:
        super().__init__(f"User with email '{email}' already exists")


class MagicLinkExpiredError(DomainException):
    """Raised when magic link has expired."""

    def __init__(self) -> None:
        super().__init__("Magic link has expired")


class MagicLinkAlreadyUsedError(DomainException):
    """Raised when magic link has already been used."""

    def __init__(self) -> None:
        super().__init__("Magic link has already been used")


class InvalidMagicLinkError(DomainException):
    """Raised when magic link is invalid."""

    def __init__(self) -> None:
        super().__init__("Invalid magic link")


class RefreshTokenMissingError(DomainException):
    """Raised when refresh token cookie is missing."""

    def __init__(self) -> None:
        super().__init__("Refresh token is missing")


class DeviceSessionNotFoundError(DomainException):
    """Raised when device session is not found."""

    def __init__(self) -> None:
        super().__init__("Device session not found")


class DeviceSessionExpiredError(DomainException):
    """Raised when device session has expired."""

    def __init__(self) -> None:
        super().__init__("Device session has expired")


class DeviceSessionRevokedError(DomainException):
    """Raised when device session has been revoked."""

    def __init__(self) -> None:
        super().__init__("Device session has been revoked")


class DeviceSessionRiskBlockedError(DomainException):
    """Raised when device session is blocked by risk checks."""

    def __init__(self) -> None:
        super().__init__("Device session requires re-authentication")
