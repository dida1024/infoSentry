"""Business event logging port."""

from abc import ABC, abstractmethod
from typing import Any

from src.core.domain.events import DomainEvent


class BusinessEventLogger(ABC):
    """Port for logging business events."""

    @abstractmethod
    async def log_event(
        self,
        event_name: str,
        event_data: dict[str, Any] | None = None,
        user_id: str | None = None,
        **kwargs,
    ) -> None:
        """Log a business event."""
        pass

    @abstractmethod
    async def log_domain_event(
        self,
        event: DomainEvent,
        **kwargs,
    ) -> None:
        """Log a domain event."""
        pass

    @abstractmethod
    async def log_error(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """Log an error with context."""
        pass

    @abstractmethod
    async def log_warning(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """Log a warning with context."""
        pass
