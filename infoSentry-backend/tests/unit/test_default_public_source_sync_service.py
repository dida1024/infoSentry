"""Tests for default public source sync service."""

from __future__ import annotations

from collections import OrderedDict

import pytest

from src.modules.sources.application.default_public_source_sync_service import (
    DefaultPublicSourceSyncService,
)
from src.modules.sources.domain.catalog import (
    NewsNowCatalog,
    NewsNowCatalogProvider,
    NewsNowCatalogSource,
)
from src.modules.sources.domain.entities import Source, SourceType

pytestmark = pytest.mark.anyio


class InMemorySourceRepository:
    """Simple in-memory repository for sync service tests."""

    def __init__(self, sources: list[Source] | None = None) -> None:
        self.sources: OrderedDict[str, Source] = OrderedDict()
        for source in sources or []:
            self.sources[source.id] = source

    async def get_by_id(self, entity_id: str) -> Source | None:
        return self.sources.get(entity_id)

    async def create(self, entity: Source) -> Source:
        self.sources[entity.id] = entity
        return entity

    async def update(self, entity: Source) -> Source:
        self.sources[entity.id] = entity
        return entity

    async def delete(self, entity: Source | str) -> bool:
        source_id = entity.id if isinstance(entity, Source) else entity
        source = self.sources.get(source_id)
        if source is None:
            return False
        source.mark_as_deleted()
        self.sources[source.id] = source
        return True

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 10,
        include_deleted: bool = False,
    ) -> tuple[list[Source], int]:
        filtered = [
            source
            for source in self.sources.values()
            if include_deleted or not source.is_deleted
        ]
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end], len(filtered)

    async def get_by_ids(self, source_ids: list[str]) -> dict[str, Source]:
        return {
            source_id: self.sources[source_id]
            for source_id in source_ids
            if source_id in self.sources
        }

    async def get_by_name(self, name: str) -> Source | None:
        for source in self.sources.values():
            if source.name == name and not source.is_deleted:
                return source
        return None

    async def list_by_type(
        self,
        source_type: SourceType | None = None,
        enabled_only: bool = True,
        require_subscription: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Source], int]:
        filtered = [source for source in self.sources.values() if not source.is_deleted]
        if source_type is not None:
            filtered = [source for source in filtered if source.type == source_type]
        if enabled_only:
            filtered = [source for source in filtered if source.enabled]
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end], len(filtered)

    async def list_public(
        self,
        source_type: SourceType | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Source], int]:
        filtered = [
            source
            for source in self.sources.values()
            if not source.is_deleted and not source.is_private
        ]
        if source_type is not None:
            filtered = [source for source in filtered if source.type == source_type]
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end], len(filtered)

    async def get_sources_due_for_fetch(
        self,
        before_time: object | None = None,
        limit: int = 10,
    ) -> list[Source]:
        del before_time
        del limit
        return []

    async def exists_by_name(self, name: str, exclude_id: str | None = None) -> bool:
        for source in self.sources.values():
            if source.is_deleted:
                continue
            if source.name != name:
                continue
            if exclude_id and source.id == exclude_id:
                continue
            return True
        return False


class StubCatalogProvider(NewsNowCatalogProvider):
    def __init__(self, catalog: NewsNowCatalog) -> None:
        self._catalog = catalog

    async def load_catalog(self) -> NewsNowCatalog:
        return self._catalog


def _catalog_source(
    source_id: str,
    *,
    name: str,
    title: str | None = None,
    interval_ms: int | None = 600_000,
    disable: bool = False,
    redirect: str | None = None,
) -> NewsNowCatalogSource:
    return NewsNowCatalogSource(
        source_id=source_id,
        name=name,
        title=title,
        interval_ms=interval_ms,
        disable=disable,
        redirect=redirect,
        raw={"name": name},
    )


async def test_sync_creates_sources_and_is_idempotent() -> None:
    repository = InMemorySourceRepository()
    catalog = NewsNowCatalog(
        sources=[
            _catalog_source("github", name="Github"),
            _catalog_source("github-trending", name="Github", title="Trending"),
            _catalog_source("v2ex", name="V2EX", disable=True),
        ],
        loaded_from="snapshot",
    )
    service = DefaultPublicSourceSyncService(
        source_repository=repository,
        catalog_provider=StubCatalogProvider(catalog),
    )

    first_result = await service.sync()
    assert first_result.created == 2
    assert first_result.disabled == 0

    second_result = await service.sync()
    assert second_result.created == 0
    assert second_result.updated == 0
    assert second_result.unchanged == 2

    public_sources = list(repository.sources.values())
    assert len(public_sources) == 2
    assert public_sources[0].config["external_key"] == "newsnow:github"
    assert public_sources[1].config["external_key"] == "newsnow:github-trending"


async def test_sync_updates_existing_and_disables_removed() -> None:
    existing_source = Source(
        id="src-1",
        type=SourceType.NEWSNOW,
        name="NewsNow | Github",
        owner_id=None,
        is_private=False,
        enabled=True,
        fetch_interval_sec=900,
        config={"external_key": "newsnow:github", "source_id": "github"},
    )
    removed_source = Source(
        id="src-2",
        type=SourceType.NEWSNOW,
        name="NewsNow | Old",
        owner_id=None,
        is_private=False,
        enabled=True,
        fetch_interval_sec=900,
        config={"external_key": "newsnow:old", "source_id": "old"},
    )
    repository = InMemorySourceRepository([existing_source, removed_source])
    catalog = NewsNowCatalog(
        sources=[
            _catalog_source(
                "github",
                name="Github",
                title="Hot",
                interval_ms=120_000,
            )
        ],
        loaded_from="remote",
    )
    service = DefaultPublicSourceSyncService(
        source_repository=repository,
        catalog_provider=StubCatalogProvider(catalog),
    )

    result = await service.sync()
    assert result.created == 0
    assert result.updated == 1
    assert result.disabled == 1

    updated = repository.sources["src-1"]
    assert updated.name == "NewsNow | Github · Hot"
    assert updated.fetch_interval_sec == 120

    disabled = repository.sources["src-2"]
    assert disabled.enabled is False


async def test_sync_resolves_name_conflicts() -> None:
    conflicting_source = Source(
        id="private-1",
        type=SourceType.RSS,
        name="NewsNow | Github",
        owner_id="user-1",
        is_private=True,
        enabled=True,
        fetch_interval_sec=600,
        config={"feed_url": "https://example.com/rss.xml"},
    )
    repository = InMemorySourceRepository([conflicting_source])
    catalog = NewsNowCatalog(
        sources=[_catalog_source("github", name="Github")],
        loaded_from="remote",
    )
    service = DefaultPublicSourceSyncService(
        source_repository=repository,
        catalog_provider=StubCatalogProvider(catalog),
    )

    result = await service.sync()
    assert result.created == 1

    created = [
        source
        for source in repository.sources.values()
        if source.config.get("external_key") == "newsnow:github"
    ][0]
    assert created.name == "NewsNow | Github [github]"
