"""Health check port."""

from abc import ABC, abstractmethod
from typing import Any


class HealthChecker(ABC):
    """Port for health check operations."""

    @abstractmethod
    async def check_health(self) -> dict[str, Any]:
        """Check health status of a component."""
        pass

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if component is healthy."""
        pass


class EmailHealthChecker(HealthChecker):
    """Port for email service health checks."""

    @abstractmethod
    async def check_email_health(self) -> dict[str, Any]:
        """Check email service health."""
        pass
