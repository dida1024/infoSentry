"""Sync default public NewsNow sources into local source registry."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from loguru import logger

from src.core.config import settings
from src.core.infrastructure.logging import get_business_logger
from src.modules.sources.domain.catalog import (
    NewsNowCatalogProvider,
    NewsNowCatalogSource,
)
from src.modules.sources.domain.entities import Source, SourceType
from src.modules.sources.domain.repository import SourceRepository


@dataclass(frozen=True)
class DefaultPublicSourceSyncResult:
    created: int
    updated: int
    disabled: int
    unchanged: int
    catalog_total: int
    active_total: int
    loaded_from: str


class DefaultPublicSourceSyncService:
    """Synchronize default public sources from NewsNow catalog."""

    def __init__(
        self,
        source_repository: SourceRepository,
        catalog_provider: NewsNowCatalogProvider,
    ) -> None:
        self.source_repository = source_repository
        self.catalog_provider = catalog_provider
        self.business_log = get_business_logger()

    async def sync(self) -> DefaultPublicSourceSyncResult:
        """Sync catalog into sources table with idempotent updates."""
        catalog = await self.catalog_provider.load_catalog()
        active_catalog_sources = [
            source for source in catalog.sources if not source.disable
        ]

        existing_sources_by_key = await self._load_existing_default_sources()
        active_external_keys: set[str] = set()

        created = 0
        updated = 0
        unchanged = 0
        disabled = 0

        for catalog_source in active_catalog_sources:
            external_key = self._external_key(catalog_source.source_id)
            active_external_keys.add(external_key)
            existing = existing_sources_by_key.get(external_key)

            desired_name = await self._resolve_unique_name(
                candidate=self._build_source_name(catalog_source),
                source_id=catalog_source.source_id,
                exclude_id=existing.id if existing else None,
            )
            desired_interval = self._resolve_interval_sec(catalog_source.interval_ms)
            desired_config = self._build_source_config(catalog_source, external_key)

            if existing is None:
                source = Source(
                    id=str(uuid4()),
                    type=SourceType.NEWSNOW,
                    name=desired_name,
                    owner_id=None,
                    is_private=False,
                    enabled=True,
                    fetch_interval_sec=desired_interval,
                    config=desired_config,
                )
                await self.source_repository.create(source)
                created += 1
                continue

            is_changed = False
            direct_fields_changed = False

            if existing.name != desired_name:
                existing.update_name(desired_name)
                is_changed = True

            if existing.fetch_interval_sec != desired_interval:
                existing.update_fetch_interval(desired_interval)
                is_changed = True

            if existing.config != desired_config:
                existing.update_config(desired_config)
                is_changed = True

            if existing.is_private:
                existing.is_private = False
                direct_fields_changed = True

            if existing.owner_id is not None:
                existing.owner_id = None
                direct_fields_changed = True

            if not existing.enabled:
                existing.enable()
                is_changed = True

            if direct_fields_changed:
                # Ensure updated_at changes even when only direct fields changed.
                existing.update_config(existing.config)
                is_changed = True

            if is_changed:
                await self.source_repository.update(existing)
                updated += 1
            else:
                unchanged += 1

        for external_key, source in existing_sources_by_key.items():
            if external_key in active_external_keys:
                continue
            if source.enabled:
                source.disable()
                await self.source_repository.update(source)
                disabled += 1

        result = DefaultPublicSourceSyncResult(
            created=created,
            updated=updated,
            disabled=disabled,
            unchanged=unchanged,
            catalog_total=len(catalog.sources),
            active_total=len(active_catalog_sources),
            loaded_from=catalog.loaded_from,
        )
        self.business_log.info(
            "default_public_sources_sync_completed",
            created=result.created,
            updated=result.updated,
            disabled=result.disabled,
            unchanged=result.unchanged,
            catalog_total=result.catalog_total,
            active_total=result.active_total,
            loaded_from=result.loaded_from,
        )
        logger.info(
            "Default public source sync completed: "
            f"created={result.created}, updated={result.updated}, "
            f"disabled={result.disabled}, unchanged={result.unchanged}, "
            f"loaded_from={result.loaded_from}"
        )
        return result

    async def _load_existing_default_sources(self) -> dict[str, Source]:
        page = 1
        page_size = settings.FORCE_INGEST_PAGE_SIZE
        result: dict[str, Source] = {}

        while True:
            sources, _ = await self.source_repository.list_by_type(
                source_type=SourceType.NEWSNOW,
                enabled_only=False,
                page=page,
                page_size=page_size,
            )
            if not sources:
                break

            for source in sources:
                external_key_value = source.config.get("external_key")
                if not isinstance(external_key_value, str):
                    continue
                if not external_key_value.startswith("newsnow:"):
                    continue
                if external_key_value in result:
                    logger.warning(
                        f"Duplicate external_key detected for sources: "
                        f"{external_key_value}"
                    )
                    continue
                result[external_key_value] = source

            if len(sources) < page_size:
                break
            page += 1

        return result

    @staticmethod
    def _external_key(source_id: str) -> str:
        return f"newsnow:{source_id}"

    @staticmethod
    def _build_source_config(
        source: NewsNowCatalogSource,
        external_key: str,
    ) -> dict[str, object]:
        config: dict[str, object] = {
            "source_id": source.source_id,
            "base_url": settings.NEWSNOW_API_BASE_URL,
            "api_path": settings.NEWSNOW_API_PATH,
            "latest": False,
            "external_key": external_key,
            "upstream_interval_ms": source.interval_ms,
        }
        if source.redirect:
            config["upstream_redirect"] = source.redirect
        return config

    @staticmethod
    def _build_source_name(source: NewsNowCatalogSource) -> str:
        prefix = settings.NEWSNOW_PUBLIC_SOURCE_PREFIX.strip()
        clean_name = source.name.strip() or source.source_id
        title = source.title.strip() if source.title else ""
        if title:
            if prefix:
                return f"{prefix} {clean_name} · {title}"
            return f"{clean_name} · {title}"
        if prefix:
            return f"{prefix} {clean_name}"
        return clean_name

    @staticmethod
    def _resolve_interval_sec(interval_ms: int | None) -> int:
        if interval_ms is None or interval_ms <= 0:
            return int(settings.NEWSNOW_FETCH_INTERVAL_SEC)
        seconds = max(1, int(round(interval_ms / 1000)))
        return max(
            int(settings.NEWSNOW_SOURCE_INTERVAL_MIN_SEC),
            min(int(settings.NEWSNOW_SOURCE_INTERVAL_MAX_SEC), seconds),
        )

    async def _resolve_unique_name(
        self,
        *,
        candidate: str,
        source_id: str,
        exclude_id: str | None,
    ) -> str:
        if not await self.source_repository.exists_by_name(
            candidate,
            exclude_id=exclude_id,
        ):
            return candidate

        with_source_id = f"{candidate} [{source_id}]"
        if not await self.source_repository.exists_by_name(
            with_source_id,
            exclude_id=exclude_id,
        ):
            return with_source_id

        suffix = 2
        while True:
            with_index = f"{with_source_id} #{suffix}"
            if not await self.source_repository.exists_by_name(
                with_index,
                exclude_id=exclude_id,
            ):
                return with_index
            suffix += 1
