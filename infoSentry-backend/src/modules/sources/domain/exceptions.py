"""Source domain exceptions."""

from src.core.domain.exceptions import DomainException, EntityNotFoundError


class SourceNotFoundError(EntityNotFoundError):
    """Raised when source is not found."""

    def __init__(self, source_id: str | None = None, name: str | None = None):
        if name:
            super().__init__("Source", name)
        else:
            super().__init__("Source", source_id)


class SourceAlreadyExistsError(DomainException):
    """Raised when source with same name already exists."""

    def __init__(self, name: str):
        super().__init__(f"Source with name '{name}' already exists")


class InvalidSourceConfigError(DomainException):
    """Raised when source configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(f"Invalid source configuration: {message}")
