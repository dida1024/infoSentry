"""Email service for sending push notifications.

Provides:
- SMTP provider abstraction
- Retry logic with exponential backoff
- Failure alerting
- Fallback to in-app only
"""

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

from src.core.config import settings
from src.core.infrastructure.health import EmailHealthResult


@dataclass
class EmailResult:
    """Email send result."""

    success: bool
    message_id: str | None = None
    error: str | None = None
    retry_count: int = 0


class SMTPProvider:
    """SMTP email provider.

    Handles:
    - Connection pooling (simplified for v0)
    - TLS/SSL support
    - Authentication
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        use_ssl: bool = False,
        from_email: str | None = None,
        from_name: str | None = None,
    ):
        self.host = host or settings.SMTP_HOST
        self.port = port or settings.SMTP_PORT
        self.user = user or settings.SMTP_USER
        self.password = password or settings.SMTP_PASSWORD
        self.use_tls = use_tls if use_tls is not None else settings.SMTP_TLS
        self.use_ssl = use_ssl if use_ssl is not None else settings.SMTP_SSL
        self.from_email = from_email or settings.EMAILS_FROM_EMAIL
        self.from_name = from_name or settings.EMAILS_FROM_NAME

    def is_configured(self) -> bool:
        """Check if SMTP is properly configured."""
        return bool(self.host and self.from_email)

    def _create_connection(self) -> smtplib.SMTP | smtplib.SMTP_SSL:
        """Create SMTP connection."""
        if self.use_ssl:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(self.host, self.port, context=context)
        else:
            server = smtplib.SMTP(self.host, self.port)
            if self.use_tls:
                context = ssl.create_default_context()
                server.starttls(context=context)

        if self.user and self.password:
            server.login(self.user, self.password)

        return server

    def send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        plain_body: str | None = None,
    ) -> EmailResult:
        """Send email synchronously.

        Args:
            to_email: Recipient email
            subject: Email subject
            html_body: HTML body
            plain_body: Plain text fallback

        Returns:
            EmailResult with success status
        """
        if not self.is_configured():
            return EmailResult(
                success=False,
                error="SMTP not configured",
            )

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            msg["Date"] = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S +0000")

            # Attach parts
            if plain_body:
                msg.attach(MIMEText(plain_body, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            # Send
            with self._create_connection() as server:
                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}")
            return EmailResult(
                success=True,
                message_id=msg.get("Message-ID"),
            )

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return EmailResult(
                success=False,
                error=f"Authentication failed: {e}",
            )
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"Recipient refused: {to_email}")
            return EmailResult(
                success=False,
                error=f"Recipient refused: {e}",
            )
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return EmailResult(
                success=False,
                error=f"SMTP error: {e}",
            )
        except Exception as e:
            logger.exception(f"Unexpected email error: {e}")
            return EmailResult(
                success=False,
                error=str(e),
            )


class EmailService:
    """Email service with retry and fallback support.

    Features:
    - Automatic retry with exponential backoff
    - Failure tracking and alerting
    - Graceful fallback to in-app notifications
    """

    def __init__(
        self,
        provider: SMTPProvider | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        self.provider = provider or SMTPProvider()
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._consecutive_failures = 0
        self._last_failure_time: datetime | None = None

    def is_available(self) -> bool:
        """Check if email service is available.

        Returns:
            True if email is enabled and configured
        """
        if not settings.EMAIL_ENABLED:
            return False
        return self.provider.is_configured()

    def is_circuit_open(self) -> bool:
        """Check if circuit breaker is open (too many failures).

        Circuit opens after 5 consecutive failures.
        Resets after 5 minutes.
        """
        if self._consecutive_failures >= 5:
            if self._last_failure_time:
                elapsed = (datetime.now(UTC) - self._last_failure_time).total_seconds()
                if elapsed < 300:  # 5 minutes
                    return True
                # Reset after 5 minutes
                self._consecutive_failures = 0
        return False

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        plain_body: str | None = None,
    ) -> EmailResult:
        """Send email with retry logic.

        Args:
            to_email: Recipient email
            subject: Email subject
            html_body: HTML body
            plain_body: Plain text fallback

        Returns:
            EmailResult with success status
        """
        if not self.is_available():
            logger.warning("Email service not available")
            return EmailResult(
                success=False,
                error="Email service not available",
            )

        if self.is_circuit_open():
            logger.warning("Email circuit breaker is open")
            return EmailResult(
                success=False,
                error="Circuit breaker open - too many failures",
            )

        # Retry loop
        last_error = None
        for attempt in range(self.max_retries):
            # Run sync SMTP in thread pool
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self.provider.send,
                to_email,
                subject,
                html_body,
                plain_body,
            )

            if result.success:
                # Reset failure counter on success
                self._consecutive_failures = 0
                result.retry_count = attempt
                return result

            last_error = result.error
            logger.warning(
                f"Email send attempt {attempt + 1}/{self.max_retries} failed: {last_error}"
            )

            # Exponential backoff
            if attempt < self.max_retries - 1:
                delay = self.base_delay * (2**attempt)
                await asyncio.sleep(delay)

        # All retries failed
        self._consecutive_failures += 1
        self._last_failure_time = datetime.now(UTC)

        logger.error(f"Email send failed after {self.max_retries} attempts")
        return EmailResult(
            success=False,
            error=last_error,
            retry_count=self.max_retries,
        )

    async def send_batch(
        self,
        emails: list[dict[str, Any]],
    ) -> list[EmailResult]:
        """Send multiple emails.

        Args:
            emails: List of email dicts with keys:
                - to_email
                - subject
                - html_body
                - plain_body (optional)

        Returns:
            List of EmailResults
        """
        results = []
        for email_data in emails:
            result = await self.send_email(
                to_email=email_data["to_email"],
                subject=email_data["subject"],
                html_body=email_data["html_body"],
                plain_body=email_data.get("plain_body"),
            )
            results.append(result)

            # Small delay between emails to avoid rate limiting
            await asyncio.sleep(0.5)

        return results

    def get_health_status(self) -> EmailHealthResult:
        """Get email service health status.

        Returns:
            EmailHealthResult: 邮件服务健康状态
        """
        return EmailHealthResult(
            available=self.is_available(),
            circuit_open=self.is_circuit_open(),
            consecutive_failures=self._consecutive_failures,
            smtp_configured=self.provider.is_configured(),
            email_enabled=settings.EMAIL_ENABLED,
        )


# Global email service instance
_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    """Get email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
