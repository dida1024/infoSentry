"""Tool: probe_rss — detect RSS/Atom feeds on a given URL."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
from loguru import logger
from pydantic_ai import RunContext

from src.modules.agent.application.discovery.tools.http_safe import (
    is_allowed_url,
    safe_get,
)

if TYPE_CHECKING:
    from src.modules.agent.application.discovery.agent import DiscoveryDeps

COMMON_FEED_PATHS = ["/rss", "/feed", "/atom.xml", "/rss.xml", "/feed.xml", "/feed/"]


async def probe_rss(
    ctx: RunContext[DiscoveryDeps],
    url: str,
) -> dict[str, Any]:
    """探测给定 URL 是否有原生 RSS/Atom feed。

    会检查 HTML 中的 <link rel="alternate"> 标签，
    以及常见的 feed 路径如 /rss, /feed, /atom.xml 等。

    Args:
        url: 要探测的网站 URL，如 "https://example.com"
    """
    if not is_allowed_url(url):
        return {"found": False, "feed_urls": [], "error": "URL 不允许访问"}

    client = ctx.deps.http_client
    timeout = ctx.deps.probe_timeout
    found_feeds: list[dict[str, Any]] = []

    try:
        # 1) Fetch page HTML and look for <link rel="alternate">
        resp = await safe_get(client, url, timeout=timeout)
        resp.raise_for_status()
        html = resp.text

        for link_type, fmt in [
            ("application/rss+xml", "rss"),
            ("application/atom+xml", "atom"),
            ("application/feed+json", "json"),
        ]:
            pattern = rf'<link[^>]+type=["\']?{re.escape(link_type)}["\']?[^>]*>'
            for match in re.finditer(pattern, html, re.IGNORECASE):
                tag = match.group(0)
                href_match = re.search(r'href=["\']?([^"\'>\s]+)', tag)
                if href_match:
                    feed_url = urljoin(url, href_match.group(1))
                    if is_allowed_url(feed_url):
                        found_feeds.append({"url": feed_url, "format": fmt, "source": "link_tag"})

        # 2) Try common feed paths
        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        for path in COMMON_FEED_PATHS:
            candidate = base + path
            if any(f["url"] == candidate for f in found_feeds):
                continue
            try:
                r = await safe_get(client, candidate, timeout=timeout)
                if r.status_code == 200:
                    ct = r.headers.get("content-type", "")
                    text = r.text[:2000]
                    if any(x in ct for x in ["xml", "rss", "atom"]) or "<rss" in text or "<feed" in text:
                        parsed = feedparser.parse(text)
                        if parsed.entries:
                            found_feeds.append({
                                "url": candidate,
                                "format": "rss" if "<rss" in text else "atom",
                                "source": "path_probe",
                                "title": parsed.feed.get("title", ""),
                            })
            except (httpx.HTTPError, httpx.TimeoutException, ValueError):
                continue

    except (httpx.HTTPError, httpx.TimeoutException, ValueError) as e:
        logger.debug(f"probe_rss failed for {url}: {e}")
        return {"found": False, "feed_urls": [], "error": str(e)}

    # 3) Validate found feeds with feedparser
    validated: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for feed in found_feeds:
        if feed["url"] in seen_urls:
            continue
        seen_urls.add(feed["url"])
        try:
            r = await safe_get(client, feed["url"], timeout=timeout)
            parsed = feedparser.parse(r.text)
            if parsed.entries:
                validated.append({
                    "url": feed["url"],
                    "title": parsed.feed.get("title", feed.get("title", "")),
                    "format": feed["format"],
                    "items_count": len(parsed.entries),
                })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError):
            continue

    return {"found": len(validated) > 0, "feed_urls": validated}
