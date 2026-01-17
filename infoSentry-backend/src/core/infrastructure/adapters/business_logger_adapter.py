"""Business event logger adapter implementation."""

from typing import Any

from src.core.domain.events import DomainEvent
from src.core.domain.ports.business_logger import BusinessEventLogger
from src.core.infrastructure.logging import BusinessEvents


class StructlogBusinessEventLogger(BusinessEventLogger):
    """Adapter for structlog-based business event logging."""

    def __init__(self, business_events: BusinessEvents):
        self.business_events = business_events

    async def log_event(
        self,
        event_name: str,
        event_data: dict[str, Any] | None = None,
        user_id: str | None = None,
        **kwargs,
    ) -> None:
        """Log a business event."""
        await self.business_events.log_event(
            event_name=event_name,
            event_data=event_data,
            user_id=user_id,
            **kwargs,
        )

    async def log_domain_event(
        self,
        event: DomainEvent,
        **kwargs,
    ) -> None:
        """Log a domain event."""
        await self.business_events.log_domain_event(event, **kwargs)

    async def log_error(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """Log an error with context."""
        await self.business_events.log_error(error, context, **kwargs)

    async def log_warning(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """Log a warning with context."""
        await self.business_events.log_warning(message, context, **kwargs)
