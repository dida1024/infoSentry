"""Base domain exceptions."""


class DomainException(Exception):
    """Base exception for all domain errors."""

    def __init__(self, message: str = "A domain error occurred"):
        self.message = message
        super().__init__(self.message)


class EntityNotFoundError(DomainException):
    """Raised when an entity is not found."""

    def __init__(self, entity_type: str, entity_id: str | None = None):
        message = f"{entity_type} not found"
        if entity_id:
            message = f"{entity_type} with id '{entity_id}' not found"
        super().__init__(message)


class DuplicateEntityError(DomainException):
    """Raised when a duplicate entity is detected."""

    def __init__(self, entity_type: str, field: str, value: str):
        message = f"{entity_type} with {field} '{value}' already exists"
        super().__init__(message)


class ValidationError(DomainException):
    """Raised when validation fails."""

    pass


class AuthorizationError(DomainException):
    """Raised when authorization fails."""

    pass


class BudgetExceededError(DomainException):
    """Raised when budget limit is exceeded."""

    pass
