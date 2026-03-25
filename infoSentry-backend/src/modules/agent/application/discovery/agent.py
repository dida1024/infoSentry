"""Discovery Agent — Pydantic AI agent for finding information sources.

Uses tool-calling to search catalogs, probe RSS feeds, query RSSHub,
analyze site HTML, validate sources, and add confirmed sources.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic_ai import Agent

from src.core.config import settings
from src.modules.agent.domain.discovery_entities import DiscoverySession
from src.modules.agent.domain.repository import DiscoveryCandidateRepository
from src.modules.sources.application.handlers import (
    CreateSourceHandler,
    SubscribeSourceHandler,
)
from src.modules.sources.application.services import SourceQueryService
from src.modules.sources.domain.catalog import NewsNowCatalogProvider
from src.modules.sources.domain.entities import SourceType
from src.modules.sources.domain.fetcher import BaseFetcher
from src.modules.sources.domain.repository import SourceRepository

# Type alias for fetcher creation callable (domain-level contract)
FetcherCreator = Callable[[SourceType, dict[str, Any]], BaseFetcher]


@dataclass
class DiscoveryDeps:
    """Runtime dependencies injected into every tool via RunContext."""

    # sources module (application/domain layer only)
    catalog_provider: NewsNowCatalogProvider
    create_fetcher: FetcherCreator
    create_source_handler: CreateSourceHandler
    subscribe_source_handler: SubscribeSourceHandler
    source_query_service: SourceQueryService
    source_repository: SourceRepository

    # discovery persistence
    candidate_repository: DiscoveryCandidateRepository

    # infra
    http_client: httpx.AsyncClient

    # session context
    session: DiscoverySession

    # config
    rsshub_base_url: str = ""
    probe_timeout: float = 10.0
    web_search_api_key: str = ""


DISCOVERY_SYSTEM_PROMPT = """\
你是信息源发现助手。用户会描述想关注的信息，你需要帮他们找到合适的信息源并添加到系统。

工作流程：
1. 理解用户意图，推断可能的平台或网站
2. 按优先级搜索：内置目录(search_catalog) → 网络搜索(web_search) → 原生RSS探测(probe_rss) → RSSHub查询(search_rsshub) → 网页分析(fetch_site_html)
3. 找到候选后，用 validate_source 验证其可用性
4. 展示验证通过的结果，等待用户确认后才调用 add_source 添加

规则：
- 每个候选源必须经过 validate_source 验证才能推荐
- 未经用户明确同意，绝不调用 add_source
- 如果所有策略都找不到可靠源，如实告知用户
- 用中文和用户交流
- 简洁地汇报进展，不要啰嗦
- 当你需要用户确认是否添加源时，清晰列出候选源的名称、类型和URL
"""

# Module-level agent instance, lazily initialized
_agent: Agent[DiscoveryDeps] | None = None


def get_discovery_agent() -> Agent[DiscoveryDeps]:
    """Get or create the discovery agent singleton.

    Deferred creation avoids requiring API keys at import time.
    """
    global _agent
    if _agent is not None:
        return _agent

    agent = Agent(
        settings.DISCOVERY_AGENT_MODEL,
        deps_type=DiscoveryDeps,
        system_prompt=DISCOVERY_SYSTEM_PROMPT,
    )

    # Register tools
    from src.modules.agent.application.discovery.tools.catalog_search import (
        search_catalog,
    )
    from src.modules.agent.application.discovery.tools.rss_probe import probe_rss
    from src.modules.agent.application.discovery.tools.rsshub_lookup import (
        search_rsshub,
    )
    from src.modules.agent.application.discovery.tools.site_html_fetcher import (
        fetch_site_html,
    )
    from src.modules.agent.application.discovery.tools.source_adder import add_source
    from src.modules.agent.application.discovery.tools.source_validator import (
        validate_source,
    )
    from src.modules.agent.application.discovery.tools.web_search import web_search

    agent.tool(search_catalog)
    agent.tool(web_search)
    agent.tool(probe_rss)
    agent.tool(search_rsshub)
    agent.tool(fetch_site_html)
    agent.tool(validate_source)
    agent.tool(add_source)

    _agent = agent
    return _agent
