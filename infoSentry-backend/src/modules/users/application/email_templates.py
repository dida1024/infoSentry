"""Email templates for user authentication."""

from datetime import datetime

from src.core.config import settings
from src.core.infrastructure.email.template_loader import render_template


def render_magic_link_email(
    *,
    to_email: str,
    login_url: str,
    expires_at: datetime,
) -> tuple[str, str, str]:
    """Render magic link email content.

    Returns:
        (subject, html_body, plain_body)
    """
    subject = f"登录链接 - {settings.PROJECT_NAME}"
    expires_str = expires_at.strftime("%Y-%m-%d %H:%M UTC")

    variables = {
        "project_name": settings.PROJECT_NAME,
        "to_email": to_email,
        "login_url": login_url,
        "expires_str": expires_str,
    }

    html_body = render_template("magic_link.html", **variables)
    plain_body = render_template("magic_link.txt", **variables)

    return subject, html_body, plain_body
