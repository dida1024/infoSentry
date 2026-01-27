"""Business event logger adapter implementation.

将 BusinessEventLogger 端口适配到 structlog 实现。
"""

from typing import Any

from src.core.domain.events import DomainEvent
from src.core.domain.ports.business_logger import BusinessEventLogger
from src.core.infrastructure.logging import BusinessEvents


class StructlogBusinessEventLogger(BusinessEventLogger):
    """Adapter for structlog-based business event logging.

    将 BusinessEventLogger 端口适配到 BusinessEvents 类的实现。
    虽然端口定义为 async 方法，但 structlog 日志记录是同步的，
    这里直接调用同步方法。
    """

    async def log_event(
        self,
        event_name: str,
        event_data: dict[str, Any] | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log a business event."""
        BusinessEvents.log_event(
            event_name=event_name,
            event_data=event_data,
            user_id=user_id,
            **kwargs,
        )

    async def log_domain_event(
        self,
        event: DomainEvent,
        **kwargs: Any,
    ) -> None:
        """Log a domain event."""
        BusinessEvents.log_domain_event(event, **kwargs)

    async def log_error(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Log an error with context."""
        BusinessEvents.log_error(error, context, **kwargs)

    async def log_warning(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Log a warning with context."""
        BusinessEvents.log_warning(message, context, **kwargs)
