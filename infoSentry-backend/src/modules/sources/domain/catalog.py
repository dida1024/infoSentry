"""NewsNow catalog domain models and ports."""

from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class NewsNowCatalogSource:
    """Catalog metadata for one upstream source."""

    source_id: str
    name: str
    title: str | None
    interval_ms: int | None
    disable: bool
    redirect: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class NewsNowCatalog:
    """Loaded catalog payload."""

    sources: list[NewsNowCatalogSource]
    loaded_from: Literal["remote", "snapshot"]


class NewsNowCatalogProvider(Protocol):
    """Port for loading NewsNow source catalog."""

    async def load_catalog(self) -> NewsNowCatalog: ...
