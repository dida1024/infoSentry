"""Health check adapter implementation."""

from typing import Any

from src.core.domain.ports.health_checker import EmailHealthChecker
from src.core.infrastructure.health import EmailHealthResult


class EmailHealthCheckerAdapter(EmailHealthChecker):
    """Adapter for email service health checks."""

    def __init__(self):
        pass

    async def check_health(self) -> dict[str, Any]:
        """Check health status of email component."""
        result = await self.check_email_health()
        return {
            "email": result.status,
            "timestamp": result.timestamp.isoformat() if result.timestamp else None,
            "message": result.error,
        }

    async def is_healthy(self) -> bool:
        """Check if email component is healthy."""
        health = await self.check_health()
        return health.get("email") == "healthy"

    async def check_email_health(self) -> EmailHealthResult:
        """Check email service health."""
        # Implementation would check SMTP connectivity, auth, etc.
        # For now, return a healthy status
        from datetime import UTC, datetime

        return EmailHealthResult(
            status="healthy",
            timestamp=datetime.now(UTC),
            error=None,
        )
