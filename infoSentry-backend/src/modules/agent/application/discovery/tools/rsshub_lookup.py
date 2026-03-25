"""Tool: search_rsshub — find RSSHub routes for a given topic/domain."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger
from pydantic_ai import RunContext

import feedparser
from src.modules.agent.application.discovery.agent import DiscoveryDeps
from src.modules.agent.application.discovery.tools.http_safe import safe_get


def _build_candidate_routes(keywords: list[str], domain: str | None) -> list[str]:
    """Generate candidate RSSHub routes from keywords and domain."""
    routes: list[str] = []

    if domain:
        clean = domain.removeprefix("www.").removeprefix("m.")
        parts = clean.replace(".", "/")
        routes.append(f"/{parts}")
        name = clean.split(".")[0]
        routes.append(f"/{name}")

    for kw in keywords:
        routes.append(f"/{kw}")

    if domain and keywords:
        clean = domain.removeprefix("www.").removeprefix("m.")
        name = clean.split(".")[0]
        for kw in keywords:
            routes.append(f"/{name}/{kw}")

    return routes


async def search_rsshub(
    ctx: RunContext[DiscoveryDeps],
    keywords: list[str],
    domain: str | None = None,
) -> dict[str, Any]:
    """查询 RSSHub 是否有匹配的路由。

    根据关键词和域名构造可能的 RSSHub 路由，并验证是否返回有效的 RSS 内容。

    Args:
        keywords: 搜索关键词列表，如 ["github", "trending"]
        domain: 可选的目标域名，如 "github.com"
    """
    base_url = ctx.deps.rsshub_base_url.rstrip("/")
    client = ctx.deps.http_client
    timeout = ctx.deps.probe_timeout
    candidates = _build_candidate_routes(keywords, domain)

    found_routes: list[dict[str, Any]] = []
    for route in candidates:
        url = f"{base_url}{route}"
        try:
            resp = await safe_get(client, url, timeout=timeout)
            if resp.status_code != 200:
                continue
            ct = resp.headers.get("content-type", "")
            text = resp.text[:3000]
            if any(x in ct for x in ["xml", "rss", "atom"]) or "<rss" in text or "<feed" in text:
                parsed = feedparser.parse(text)
                if parsed.entries:
                    found_routes.append({
                        "route": route,
                        "title": parsed.feed.get("title", ""),
                        "item_count": len(parsed.entries),
                        "full_url": url,
                    })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as e:
            logger.debug(f"RSSHub route {route} failed: {e}")
            continue

        if len(found_routes) >= 3:
            break

    return {
        "found": len(found_routes) > 0,
        "routes": found_routes,
        "tried": len(candidates),
    }
