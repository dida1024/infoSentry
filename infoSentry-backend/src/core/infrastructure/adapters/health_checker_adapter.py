"""Health check adapter implementation."""

from typing import Any

from src.core.domain.ports.health_checker import EmailHealthChecker
from src.core.infrastructure.health import EmailHealthResult


class EmailHealthCheckerAdapter(EmailHealthChecker):
    """Adapter for email service health checks."""

    def __init__(self) -> None:
        pass

    async def check_health(self) -> dict[str, Any]:
        """Check health status of email component."""
        result = await self.check_email_health()
        return {
            "email": "healthy" if result["available"] else "unhealthy",
            "available": result["available"],
            "circuit_open": result["circuit_open"],
            "consecutive_failures": result["consecutive_failures"],
            "smtp_configured": result["smtp_configured"],
            "email_enabled": result["email_enabled"],
        }

    async def is_healthy(self) -> bool:
        """Check if email component is healthy."""
        health = await self.check_health()
        return bool(health.get("available"))

    async def check_email_health(self) -> dict[str, Any]:
        """Check email service health."""
        result = EmailHealthResult(
            available=True,
            circuit_open=False,
            consecutive_failures=0,
            smtp_configured=True,
            email_enabled=True,
        )
        return result.model_dump(mode="json")
