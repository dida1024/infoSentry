"""抓取器基类定义。"""

from src.modules.sources.domain.fetcher import (  # re-export for backward compatibility
    BaseFetcher,
    FetchedItem,
    FetchResult,
    FetchStatus,
)

__all__ = ["BaseFetcher", "FetchResult", "FetchStatus", "FetchedItem"]
