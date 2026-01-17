"""Email templates for push notifications.

Includes templates for:
- Immediate: 即时推送（高价值新闻）
- Batch: 批量推送（窗口内的新闻汇总）
- Digest: 每日摘要
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class EmailItem:
    """Email item data structure."""

    item_id: str
    title: str
    snippet: str | None
    url: str
    source_name: str | None
    published_at: datetime | None
    reason: str
    redirect_url: str  # /r/{item_id}?goal_id=xxx


@dataclass
class EmailData:
    """Email data structure."""

    to_email: str
    goal_id: str
    goal_name: str
    items: list[EmailItem]
    decision_ids: list[str]


def build_redirect_url(
    base_url: str,
    item_id: str,
    goal_id: str,
    channel: str = "email",
    api_prefix: str = "/api/v1",
) -> str:
    """Build redirect URL for click tracking."""
    normalized_base = base_url.rstrip("/")
    normalized_prefix = api_prefix.rstrip("/")
    if normalized_prefix and not normalized_base.endswith(normalized_prefix):
        normalized_base = f"{normalized_base}{normalized_prefix}"
    return (
        f"{normalized_base}/r/{item_id}"
        f"?goal_id={goal_id}&channel={channel}"
    )


def render_immediate_email(
    data: EmailData,
    base_url: str = "http://localhost:8000",
) -> tuple[str, str]:
    """Render immediate email.

    Args:
        data: Email data
        base_url: Backend base URL for redirect links

    Returns:
        (subject, html_body)
    """
    subject = f"🔔 高优先级更新: {data.goal_name}"

    # Build items HTML
    items_html = ""
    for item in data.items:
        published_str = ""
        if item.published_at:
            published_str = item.published_at.strftime("%Y-%m-%d %H:%M")

        items_html += f"""
        <div style="margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #dc3545;">
            <h3 style="margin: 0 0 10px 0; font-size: 16px;">
                <a href="{item.redirect_url}" style="color: #1a73e8; text-decoration: none;">
                    {item.title}
                </a>
            </h3>
            {f'<p style="margin: 0 0 10px 0; color: #666; font-size: 14px; line-height: 1.5;">{item.snippet}</p>' if item.snippet else ""}
            <p style="margin: 0; font-size: 12px; color: #999;">
                {f"📰 {item.source_name} · " if item.source_name else ""}{published_str}
            </p>
            <p style="margin: 10px 0 0 0; font-size: 13px; color: #28a745;">
                💡 {item.reason}
            </p>
        </div>
        """

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #ffffff;">
        <div style="text-align: center; padding: 20px 0; border-bottom: 1px solid #eee;">
            <h1 style="margin: 0; font-size: 24px; color: #333;">🎯 {data.goal_name}</h1>
            <p style="margin: 10px 0 0 0; color: #666;">发现以下高价值内容</p>
        </div>

        <div style="padding: 20px 0;">
            {items_html}
        </div>

        <div style="text-align: center; padding: 20px; border-top: 1px solid #eee; color: #999; font-size: 12px;">
            <p>来自 <strong>infoSentry</strong> 的即时推送</p>
            <p>
                <a href="{base_url}/goals/{data.goal_id}" style="color: #1a73e8;">查看目标设置</a> ·
                <a href="{base_url}/inbox" style="color: #1a73e8;">查看收件箱</a>
            </p>
        </div>
    </body>
    </html>
    """

    return subject, html_body


def render_batch_email(
    data: EmailData,
    window_time: str,
    base_url: str = "http://localhost:8000",
) -> tuple[str, str]:
    """Render batch email.

    Args:
        data: Email data
        window_time: Batch window time (e.g., "12:30")
        base_url: Backend base URL

    Returns:
        (subject, html_body)
    """
    item_count = len(data.items)
    subject = f"📬 {data.goal_name} - {window_time} 更新 ({item_count}条)"

    # Build items HTML
    items_html = ""
    for i, item in enumerate(data.items, 1):
        published_str = ""
        if item.published_at:
            published_str = item.published_at.strftime("%Y-%m-%d %H:%M")

        items_html += f"""
        <div style="margin-bottom: 16px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
            <h3 style="margin: 0 0 8px 0; font-size: 15px;">
                <span style="color: #999; font-weight: normal;">{i}.</span>
                <a href="{item.redirect_url}" style="color: #1a73e8; text-decoration: none;">
                    {item.title}
                </a>
            </h3>
            {f'<p style="margin: 0 0 8px 0; color: #666; font-size: 13px; line-height: 1.4;">{item.snippet[:150]}...</p>' if item.snippet and len(item.snippet) > 150 else f'<p style="margin: 0 0 8px 0; color: #666; font-size: 13px; line-height: 1.4;">{item.snippet}</p>' if item.snippet else ""}
            <p style="margin: 0; font-size: 11px; color: #999;">
                {f"{item.source_name} · " if item.source_name else ""}{published_str}
            </p>
        </div>
        """

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #ffffff;">
        <div style="text-align: center; padding: 20px 0; border-bottom: 1px solid #eee;">
            <h1 style="margin: 0; font-size: 22px; color: #333;">📬 定时更新</h1>
            <p style="margin: 10px 0 0 0; color: #666;">
                <strong>{data.goal_name}</strong> · {window_time}
            </p>
        </div>

        <div style="padding: 20px 0;">
            <p style="margin: 0 0 16px 0; color: #666; font-size: 14px;">
                为您找到 <strong>{item_count}</strong> 条相关内容：
            </p>
            {items_html}
        </div>

        <div style="text-align: center; padding: 20px; border-top: 1px solid #eee; color: #999; font-size: 12px;">
            <p>来自 <strong>infoSentry</strong> 的批量推送</p>
            <p>
                <a href="{base_url}/goals/{data.goal_id}" style="color: #1a73e8;">管理目标</a> ·
                <a href="{base_url}/inbox" style="color: #1a73e8;">查看全部</a>
            </p>
        </div>
    </body>
    </html>
    """

    return subject, html_body


def render_digest_email(
    data: EmailData,
    date_str: str,
    base_url: str = "http://localhost:8000",
) -> tuple[str, str]:
    """Render daily digest email.

    Args:
        data: Email data
        date_str: Date string (e.g., "2025-01-07")
        base_url: Backend base URL

    Returns:
        (subject, html_body)
    """
    item_count = len(data.items)
    subject = f"📋 每日摘要: {data.goal_name} ({date_str})"

    # Build items HTML with alternating colors
    items_html = ""
    for i, item in enumerate(data.items, 1):
        bg_color = "#f8f9fa" if i % 2 == 1 else "#ffffff"
        published_str = ""
        if item.published_at:
            published_str = item.published_at.strftime("%m-%d %H:%M")

        items_html += f"""
        <tr style="background: {bg_color};">
            <td style="padding: 12px; vertical-align: top; width: 30px; color: #999; font-size: 14px;">{i}</td>
            <td style="padding: 12px;">
                <a href="{item.redirect_url}" style="color: #1a73e8; text-decoration: none; font-size: 14px; font-weight: 500;">
                    {item.title}
                </a>
                <div style="margin-top: 4px; font-size: 12px; color: #999;">
                    {f"{item.source_name} · " if item.source_name else ""}{published_str}
                </div>
            </td>
        </tr>
        """

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #ffffff;">
        <div style="text-align: center; padding: 20px 0; border-bottom: 1px solid #eee;">
            <h1 style="margin: 0; font-size: 22px; color: #333;">📋 每日摘要</h1>
            <p style="margin: 10px 0 0 0; color: #666;">{date_str}</p>
        </div>

        <div style="padding: 20px 0;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 15px 20px; border-radius: 8px; margin-bottom: 20px;">
                <h2 style="margin: 0; color: #fff; font-size: 18px;">🎯 {data.goal_name}</h2>
                <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.8); font-size: 14px;">
                    今日共 {item_count} 条相关内容
                </p>
            </div>

            <table style="width: 100%; border-collapse: collapse; border: 1px solid #eee; border-radius: 8px; overflow: hidden;">
                {items_html}
            </table>
        </div>

        <div style="text-align: center; padding: 20px;">
            <a href="{base_url}/inbox?goal_id={data.goal_id}" style="display: inline-block; padding: 12px 24px; background: #1a73e8; color: #fff; text-decoration: none; border-radius: 6px; font-size: 14px;">
                查看全部内容
            </a>
        </div>

        <div style="text-align: center; padding: 20px; border-top: 1px solid #eee; color: #999; font-size: 12px;">
            <p>来自 <strong>infoSentry</strong> 的每日摘要</p>
            <p>
                <a href="{base_url}/goals/{data.goal_id}/settings" style="color: #1a73e8;">调整推送设置</a>
            </p>
        </div>
    </body>
    </html>
    """

    return subject, html_body


def render_plain_text_fallback(data: EmailData) -> str:
    """Render plain text fallback for email clients that don't support HTML.

    Args:
        data: Email data

    Returns:
        Plain text body
    """
    lines = [
        f"{'=' * 50}",
        f"infoSentry - {data.goal_name}",
        f"{'=' * 50}",
        "",
    ]

    for i, item in enumerate(data.items, 1):
        lines.append(f"{i}. {item.title}")
        if item.snippet:
            lines.append(f"   {item.snippet[:100]}...")
        lines.append(f"   链接: {item.redirect_url}")
        if item.source_name:
            lines.append(f"   来源: {item.source_name}")
        lines.append("")

    lines.extend(
        [
            f"{'=' * 50}",
            "此邮件由 infoSentry 自动发送",
        ]
    )

    return "\n".join(lines)
