"""Goal domain exceptions."""

from src.core.domain.exceptions import DomainException, EntityNotFoundError


class GoalNotFoundError(EntityNotFoundError):
    """Raised when goal is not found."""

    def __init__(self, goal_id: str):
        super().__init__("Goal", goal_id)


class GoalAccessDeniedError(DomainException):
    """Raised when user doesn't have access to goal."""

    def __init__(self, goal_id: str):
        super().__init__(f"Access denied to goal '{goal_id}'")


class InvalidBatchWindowError(DomainException):
    """Raised when batch window format is invalid."""

    def __init__(self, window: str):
        super().__init__(f"Invalid batch window format: '{window}'. Expected HH:MM")


class TooManyBatchWindowsError(DomainException):
    """Raised when too many batch windows are specified."""

    def __init__(self):
        super().__init__("Maximum 3 batch windows allowed")
