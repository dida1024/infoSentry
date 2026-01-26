"""User-related Celery tasks."""

import asyncio

from celery import shared_task
from loguru import logger

from src.core.config import settings
from src.core.infrastructure.celery.queues import Queues
from src.core.infrastructure.celery.retry import (
    DEFAULT_RETRYABLE_EXCEPTIONS,
    RetryableTaskError,
)
from src.core.infrastructure.logging import BusinessEvents


@shared_task(
    name="src.modules.users.tasks.send_magic_link_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=DEFAULT_RETRYABLE_EXCEPTIONS,
    retry_backoff=True,
    queue=Queues.EMAIL,
)
def send_magic_link_email(_self: object, magic_link_id: str, email: str) -> None:
    """Send magic link email for login."""
    asyncio.run(_send_magic_link_email_async(magic_link_id, email))


async def _send_magic_link_email_async(
    magic_link_id: str,
    email: str,
) -> None:
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.modules.push.application.email_service import get_email_service
    from src.modules.users.application.email_templates import render_magic_link_email
    from src.modules.users.infrastructure.mappers import MagicLinkMapper
    from src.modules.users.infrastructure.repositories import (
        PostgreSQLMagicLinkRepository,
    )

    async with get_async_session() as session:
        try:
            event_bus = SimpleEventBus()
            magic_link_repo = PostgreSQLMagicLinkRepository(
                session, MagicLinkMapper(), event_bus
            )
            magic_link = await magic_link_repo.get_by_id(magic_link_id)

            if not magic_link:
                logger.warning(
                    f"Magic link not found for email task: id={magic_link_id}"
                )
                BusinessEvents.magic_link_email_sent(
                    email=email,
                    magic_link_id=magic_link_id,
                    success=False,
                    error="magic_link_not_found",
                )
                return

            if not magic_link.is_valid():
                logger.warning(f"Magic link invalid for email task: id={magic_link_id}")
                BusinessEvents.magic_link_email_sent(
                    email=magic_link.email,
                    magic_link_id=magic_link_id,
                    success=False,
                    error="magic_link_invalid",
                )
                return

            login_url = (
                f"{settings.FRONTEND_HOST.rstrip('/')}/auth/callback"
                f"?token={magic_link.token}"
            )

            subject, html_body, plain_body = render_magic_link_email(
                to_email=magic_link.email,
                login_url=login_url,
                expires_at=magic_link.expires_at,
            )

            email_service = get_email_service()
            if not email_service.is_available():
                BusinessEvents.magic_link_email_sent(
                    email=magic_link.email,
                    magic_link_id=magic_link_id,
                    success=False,
                    error="email_service_unavailable",
                )
                return

            result = await email_service.send_email(
                to_email=magic_link.email,
                subject=subject,
                html_body=html_body,
                plain_body=plain_body,
            )

            if result.success:
                BusinessEvents.magic_link_email_sent(
                    email=magic_link.email,
                    magic_link_id=magic_link_id,
                    success=True,
                )
                return

            BusinessEvents.magic_link_email_sent(
                email=magic_link.email,
                magic_link_id=magic_link_id,
                success=False,
                error=result.error or "send_failed",
            )
            raise RetryableTaskError(
                f"Failed to send magic link email: {result.error or 'send_failed'}"
            )
        except Exception as exc:
            logger.exception(f"Error sending magic link email: {exc}")
            await session.rollback()
            raise
