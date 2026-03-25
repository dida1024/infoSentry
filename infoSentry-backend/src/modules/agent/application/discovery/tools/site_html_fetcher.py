"""Tool: fetch_site_html — fetch and clean HTML for agent analysis."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import httpx
from loguru import logger
from pydantic_ai import RunContext

from src.modules.agent.application.discovery.tools.http_safe import (
    is_allowed_url,
    safe_get,
)

if TYPE_CHECKING:
    from src.modules.agent.application.discovery.agent import DiscoveryDeps


def _clean_html(html: str, max_chars: int = 8000) -> str:
    """Remove script/style/nav/footer, keep main content structure."""
    html = re.sub(
        r"<(script|style|noscript)[^>]*>.*?</\1>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(
        r"<(nav|footer|header|aside)[^>]*>.*?</\1>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    html = re.sub(r"\s+", " ", html).strip()
    if len(html) > max_chars:
        html = html[:max_chars] + "... [truncated]"
    return html


async def fetch_site_html(
    ctx: RunContext[DiscoveryDeps],
    url: str,
) -> dict[str, Any]:
    """获取网页的简化 HTML 结构。

    用于分析网页 DOM 结构，以便推断 CSS selectors 构建 SITE 类型源配置。
    这是最后手段，仅在其他策略（RSS、RSSHub等）都失败时使用。

    Args:
        url: 目标网页 URL，如 "https://example.gov.cn/news/"
    """
    if not is_allowed_url(url):
        return {"url": url, "html_snippet": "", "error": "URL 不允许访问"}

    client = ctx.deps.http_client
    timeout = ctx.deps.probe_timeout
    try:
        resp = await safe_get(
            client,
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; InfoSentry/1.0)"},
        )
        resp.raise_for_status()
        encoding = resp.encoding or "utf-8"
        html_snippet = _clean_html(resp.text)
        return {"url": url, "html_snippet": html_snippet, "encoding": encoding}
    except (httpx.HTTPError, httpx.TimeoutException, ValueError) as e:
        logger.debug(f"fetch_site_html failed for {url}: {e}")
        return {"url": url, "html_snippet": "", "error": str(e)}
