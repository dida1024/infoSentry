"""Base domain exceptions.

所有领域异常都应继承自 DomainException，并可以通过定义 http_status_code 和 error_code
类属性来指定 HTTP 响应细节。
"""

from fastapi import status


class DomainException(Exception):
    """Base exception for all domain errors.

    子类可以通过定义以下类属性来自定义 HTTP 响应：
    - http_status_code: HTTP 状态码（默认 400）
    - error_code: 错误代码字符串（默认 "DOMAIN_ERROR"）
    """

    http_status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "DOMAIN_ERROR"

    def __init__(self, message: str = "A domain error occurred"):
        self.message = message
        super().__init__(self.message)


class EntityNotFoundError(DomainException):
    """Raised when an entity is not found."""

    http_status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"

    def __init__(self, entity_type: str, entity_id: str | None = None):
        message = f"{entity_type} not found"
        if entity_id:
            message = f"{entity_type} with id '{entity_id}' not found"
        super().__init__(message)


class DuplicateEntityError(DomainException):
    """Raised when a duplicate entity is detected."""

    http_status_code = status.HTTP_409_CONFLICT
    error_code = "DUPLICATE_ENTITY"

    def __init__(self, entity_type: str, field: str, value: str):
        message = f"{entity_type} with {field} '{value}' already exists"
        super().__init__(message)


class ValidationError(DomainException):
    """Raised when validation fails."""

    http_status_code = status.HTTP_400_BAD_REQUEST
    error_code = "VALIDATION_ERROR"


class AuthorizationError(DomainException):
    """Raised when authorization fails."""

    http_status_code = status.HTTP_403_FORBIDDEN
    error_code = "FORBIDDEN"


class BudgetExceededError(DomainException):
    """Raised when budget limit is exceeded."""

    http_status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "BUDGET_EXCEEDED"
