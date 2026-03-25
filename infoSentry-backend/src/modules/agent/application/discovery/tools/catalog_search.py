"""Tool: search_catalog — search the built-in NewsNow source catalog."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import RunContext

from src.modules.sources.domain.entities import SourceType

if TYPE_CHECKING:
    from src.modules.agent.application.discovery.agent import DiscoveryDeps


async def search_catalog(
    ctx: RunContext[DiscoveryDeps],
    keywords: list[str],
) -> dict[str, Any]:
    """搜索内置信息源目录。根据关键词模糊匹配已有的新闻源。

    Args:
        keywords: 搜索关键词列表，如 ["深圳", "房产"]
    """
    catalog = await ctx.deps.catalog_provider.load_catalog()
    keywords_lower = [k.lower() for k in keywords]

    matches: list[dict[str, Any]] = []
    for src in catalog.sources:
        if src.disable:
            continue
        name_lower = src.name.lower()
        title_lower = (src.title or "").lower()
        if any(kw in name_lower or kw in title_lower for kw in keywords_lower):
            already_exists = await ctx.deps.source_repository.exists_by_config_url(
                source_type=SourceType.NEWSNOW,
                url=src.source_id,
            )
            matches.append(
                {
                    "source_id": src.source_id,
                    "name": src.name,
                    "title": src.title,
                    "already_exists": already_exists,
                }
            )
        if len(matches) >= 10:
            break

    return {
        "found": len(matches),
        "matches": matches,
        "catalog_size": len(catalog.sources),
    }
