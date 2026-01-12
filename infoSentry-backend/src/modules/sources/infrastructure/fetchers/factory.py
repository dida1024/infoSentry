"""抓取器工厂。

根据源类型创建相应的抓取器实例。
"""

from typing import Any

from src.core.config import settings
from src.modules.sources.domain.entities import SourceType
from src.modules.sources.infrastructure.fetchers.base import BaseFetcher
from src.modules.sources.infrastructure.fetchers.newsnow import NewsNowFetcher
from src.modules.sources.infrastructure.fetchers.rss import RSSFetcher
from src.modules.sources.infrastructure.fetchers.site import SiteFetcher


class FetcherFactory:
    """抓取器工厂类。"""

    @staticmethod
    def create(
        source_type: SourceType,
        config: dict[str, Any],
        max_items: int | None = None,
    ) -> BaseFetcher:
        """根据源类型创建抓取器。

        Args:
            source_type: 源类型
            config: 源配置
            max_items: 单次抓取最大条目数，不指定则使用默认配置

        Returns:
            对应的抓取器实例

        Raises:
            ValueError: 不支持的源类型
        """
        if max_items is None:
            max_items = settings.ITEMS_PER_SOURCE_PER_FETCH

        fetcher_map: dict[SourceType, type[BaseFetcher]] = {
            SourceType.NEWSNOW: NewsNowFetcher,
            SourceType.RSS: RSSFetcher,
            SourceType.SITE: SiteFetcher,
        }

        fetcher_class = fetcher_map.get(source_type)
        if fetcher_class is None:
            raise ValueError(f"Unsupported source type: {source_type}")

        return fetcher_class(config=config, max_items=max_items)

    @staticmethod
    def get_default_interval(source_type: SourceType) -> int:
        """获取源类型的默认抓取间隔（秒）。"""
        interval_map = {
            SourceType.NEWSNOW: settings.NEWSNOW_FETCH_INTERVAL_SEC,
            SourceType.RSS: settings.RSS_FETCH_INTERVAL_SEC,
            SourceType.SITE: settings.SITE_FETCH_INTERVAL_SEC,
        }
        return interval_map.get(source_type, 1800)


class InfrastructureFetcherFactory:
    """Adapter to expose fetcher factory via interface instance."""

    def create(
        self,
        source_type: SourceType,
        config: dict[str, Any],
        max_items: int | None = None,
    ) -> BaseFetcher:
        return FetcherFactory.create(
            source_type=source_type,
            config=config,
            max_items=max_items,
        )

    def get_default_interval(self, source_type: SourceType) -> int:
        return FetcherFactory.get_default_interval(source_type)
