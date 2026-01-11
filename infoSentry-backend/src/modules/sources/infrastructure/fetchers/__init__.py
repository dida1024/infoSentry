"""信息源抓取器模块。"""

from src.modules.sources.infrastructure.fetchers.base import (
    BaseFetcher,
    FetchedItem,
    FetchResult,
)
from src.modules.sources.infrastructure.fetchers.factory import FetcherFactory
from src.modules.sources.infrastructure.fetchers.newsnow import NewsNowFetcher
from src.modules.sources.infrastructure.fetchers.rss import RSSFetcher
from src.modules.sources.infrastructure.fetchers.site import SiteFetcher

__all__ = [
    "BaseFetcher",
    "FetchedItem",
    "FetchResult",
    "NewsNowFetcher",
    "RSSFetcher",
    "SiteFetcher",
    "FetcherFactory",
]
