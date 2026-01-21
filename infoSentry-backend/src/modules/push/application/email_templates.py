"""Email templates for push notifications.

Includes templates for:
- Immediate: 即时推送（高价值新闻）
- Batch: 批量推送（窗口内的新闻汇总）
- Digest: 每日摘要
"""

from dataclasses import dataclass
from datetime import datetime

from src.core.infrastructure.email.template_loader import render_template


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


def _prepare_items_for_template(items: list[EmailItem]) -> list[dict[str, object]]:
    """Convert EmailItem list to template-friendly format."""
    result: list[dict[str, object]] = []
    for item in items:
        published_str = ""
        if item.published_at:
            published_str = item.published_at.strftime("%Y-%m-%d %H:%M")
        result.append({
            "title": item.title,
            "snippet": item.snippet,
            "redirect_url": item.redirect_url,
            "source_name": item.source_name,
            "published_str": published_str,
            "reason": item.reason,
        })
    return result


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

    html_body = render_template(
        "push_immediate.html",
        goal_name=data.goal_name,
        goal_id=data.goal_id,
        items=_prepare_items_for_template(data.items),
        base_url=base_url,
    )

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

    html_body = render_template(
        "push_batch.html",
        goal_name=data.goal_name,
        goal_id=data.goal_id,
        window_time=window_time,
        item_count=item_count,
        items=_prepare_items_for_template(data.items),
        base_url=base_url,
    )

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

    # Prepare items with short date format for digest
    items_for_template: list[dict[str, object]] = []
    for item in data.items:
        published_str = ""
        if item.published_at:
            published_str = item.published_at.strftime("%m-%d %H:%M")
        items_for_template.append({
            "title": item.title,
            "redirect_url": item.redirect_url,
            "source_name": item.source_name,
            "published_str": published_str,
        })

    html_body = render_template(
        "push_digest.html",
        goal_name=data.goal_name,
        goal_id=data.goal_id,
        date_str=date_str,
        item_count=item_count,
        items=items_for_template,
        base_url=base_url,
    )

    return subject, html_body


def render_plain_text_fallback(data: EmailData) -> str:
    """Render plain text fallback for email clients that don't support HTML.

    Args:
        data: Email data

    Returns:
        Plain text body
    """
    # Prepare items for template
    items_for_template: list[dict[str, object]] = []
    for item in data.items:
        items_for_template.append({
            "title": item.title,
            "snippet": item.snippet,
            "redirect_url": item.redirect_url,
            "source_name": item.source_name,
        })

    return render_template(
        "push_plain.txt",
        goal_name=data.goal_name,
        items=items_for_template,
    )
