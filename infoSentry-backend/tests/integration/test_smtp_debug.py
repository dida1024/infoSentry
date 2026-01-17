import os

import pytest

from src.modules.push.application.email_service import EmailService, SMTPProvider

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


def _get_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


@pytest.mark.anyio
async def test_smtp_debug_send():
    """SMTP 调试测试：仅在显式开启时运行。"""
    if _get_env("SMTP_DEBUG") != "1":
        pytest.skip("Set SMTP_DEBUG=1 to run SMTP debug test.")

    to_email = _get_env("SMTP_DEBUG_TO")
    if not to_email:
        pytest.skip("Set SMTP_DEBUG_TO to a recipient address.")

    provider = SMTPProvider()
    print(
        "[smtp-debug] config",
        {
            "host": provider.host,
            "port": provider.port,
            "user": provider.user,
            "password_set": bool(provider.password),
            "use_tls": provider.use_tls,
            "use_ssl": provider.use_ssl,
            "from_email": provider.from_email,
            "from_name": provider.from_name,
        },
    )
    if not provider.is_configured():
        pytest.skip("SMTP not configured (SMTP_HOST / EMAILS_FROM_EMAIL missing).")


    subject = "infoSentry SMTP debug test"
    html_body = "<p>SMTP debug test from infoSentry.</p>"
    plain_body = "SMTP debug test from infoSentry."

    service = EmailService(provider=provider, max_retries=1, base_delay=0.1)
    result = await service.send_email(
        to_email=to_email,
        subject=subject,
        html_body=html_body,
        plain_body=plain_body,
    )

    assert result.success, result.error
