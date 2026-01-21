"""Email templates for user authentication."""

from datetime import datetime

from src.core.config import settings


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

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #ffffff;">
        <div style="text-align: center; padding: 20px 0; border-bottom: 1px solid #eee;">
            <h1 style="margin: 0; font-size: 22px; color: #333;">🔐 登录 {settings.PROJECT_NAME}</h1>
            <p style="margin: 10px 0 0 0; color: #666;">点击下方按钮完成登录</p>
        </div>

        <div style="padding: 24px 0; text-align: center;">
            <a href="{login_url}" style="display: inline-block; padding: 12px 24px; background: #1a73e8; color: #fff; text-decoration: none; border-radius: 6px; font-size: 14px;">
                继续登录
            </a>
            <p style="margin: 16px 0 0 0; color: #999; font-size: 12px;">
                链接将在 {expires_str} 过期
            </p>
        </div>

        <div style="padding: 12px 0; color: #666; font-size: 13px; line-height: 1.5;">
            <p style="margin: 0 0 8px 0;">
                如果按钮不可用，请复制以下链接到浏览器中打开：
            </p>
            <p style="margin: 0; word-break: break-all;">
                <a href="{login_url}" style="color: #1a73e8;">{login_url}</a>
            </p>
        </div>

        <div style="text-align: center; padding: 20px; border-top: 1px solid #eee; color: #999; font-size: 12px;">
            <p>如果你没有请求登录，请忽略此邮件。</p>
            <p>此邮件发送至 {to_email}</p>
        </div>
    </body>
    </html>
    """

    plain_body = "\n".join(
        [
            f"{settings.PROJECT_NAME} 登录链接",
            "",
            "请打开以下链接完成登录：",
            login_url,
            "",
            f"链接将在 {expires_str} 过期。",
            "如果你没有请求登录，请忽略此邮件。",
        ]
    )

    return subject, html_body, plain_body
