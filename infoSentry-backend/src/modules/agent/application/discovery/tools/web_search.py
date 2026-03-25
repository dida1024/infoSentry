"""Tool: web_search — search the web for relevant URLs."""

from __future__ import annotations

from typing import Any

from loguru import logger
from pydantic_ai import RunContext

from src.modules.agent.application.discovery.agent import DiscoveryDeps


async def web_search(
    ctx: RunContext[DiscoveryDeps],
    query: str,
) -> dict[str, Any]:
    """通过搜索引擎查找相关平台和网站URL。

    Args:
        query: 搜索查询字符串，如 "深圳住建局 官网 RSS"
    """
    api_key = ctx.deps.web_search_api_key
    if not api_key:
        return {"results": [], "error": "搜索引擎 API key 未配置，跳过网络搜索"}

    try:
        from tavily import AsyncTavilyClient

        client = AsyncTavilyClient(api_key=api_key)
        response = await client.search(
            query=query,
            max_results=5,
            search_depth="basic",
        )
        results = [
            {
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "snippet": r.get("content", "")[:200],
            }
            for r in response.get("results", [])
        ]
        return {"results": results}
    except Exception as e:
        logger.warning(f"Web search failed: {e}")
        return {"results": [], "error": f"搜索失败: {type(e).__name__}"}
