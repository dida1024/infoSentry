"""Infrastructure provider for NewsNow catalog."""

from __future__ import annotations

import json
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger

from src.core.config import settings
from src.modules.sources.domain.catalog import (
    NewsNowCatalog,
    NewsNowCatalogProvider,
    NewsNowCatalogSource,
)


class InfrastructureNewsNowCatalogProvider(NewsNowCatalogProvider):
    """Load NewsNow catalog from remote URL with snapshot fallback."""

    def __init__(
        self,
        *,
        catalog_url: str | None = None,
        timeout_sec: float | None = None,
        snapshot_path: Path | None = None,
    ) -> None:
        self.catalog_url = catalog_url or settings.NEWSNOW_CATALOG_URL
        self.timeout_sec = timeout_sec or settings.NEWSNOW_CATALOG_FETCH_TIMEOUT_SEC
        self.snapshot_path = snapshot_path or (
            Path(__file__).resolve().parents[4]
            / "resources"
            / "sources"
            / "newsnow_sources_snapshot.json"
        )

    async def load_catalog(self) -> NewsNowCatalog:
        """Load catalog from remote, then fallback to local snapshot."""
        try:
            sources = await self._load_catalog_from_remote()
            return NewsNowCatalog(sources=sources, loaded_from="remote")
        except (
            httpx.HTTPError,
            ValueError,
            json.JSONDecodeError,
            OSError,
        ) as exc:
            logger.warning(f"Failed to load NewsNow catalog remotely: {exc}")

        sources = self._load_catalog_from_snapshot()
        return NewsNowCatalog(sources=sources, loaded_from="snapshot")

    async def _load_catalog_from_remote(self) -> list[NewsNowCatalogSource]:
        if not self._is_allowed_public_http_url(self.catalog_url):
            raise ValueError("NEWSNOW_CATALOG_URL must be a public HTTP(S) URL")

        async with httpx.AsyncClient(
            timeout=self.timeout_sec,
            follow_redirects=False,
        ) as client:
            response = await client.get(
                self.catalog_url,
                headers={
                    "User-Agent": settings.FETCHER_USER_AGENT,
                    "Accept": "application/json",
                },
            )
            if 300 <= response.status_code < 400:
                raise ValueError("Redirect is not allowed for NewsNow catalog fetch")
            response.raise_for_status()
            payload = response.json()
            return self._parse_catalog_payload(payload)

    def _load_catalog_from_snapshot(self) -> list[NewsNowCatalogSource]:
        payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        return self._parse_catalog_payload(payload)

    @staticmethod
    def _parse_catalog_payload(payload: Any) -> list[NewsNowCatalogSource]:
        if not isinstance(payload, dict):
            raise ValueError("NewsNow catalog payload must be a JSON object")

        parsed_sources: list[NewsNowCatalogSource] = []
        for source_id, raw_value in payload.items():
            if not isinstance(source_id, str):
                continue
            if not isinstance(raw_value, dict):
                continue

            name_value = raw_value.get("name")
            name = name_value.strip() if isinstance(name_value, str) else source_id

            title_value = raw_value.get("title")
            title = title_value.strip() if isinstance(title_value, str) else None

            interval_value = raw_value.get("interval")
            interval_ms = interval_value if isinstance(interval_value, int) else None

            disable_value = raw_value.get("disable")
            disable = disable_value is True

            redirect_value = raw_value.get("redirect")
            redirect = redirect_value if isinstance(redirect_value, str) else None

            parsed_sources.append(
                NewsNowCatalogSource(
                    source_id=source_id,
                    name=name,
                    title=title,
                    interval_ms=interval_ms,
                    disable=disable,
                    redirect=redirect,
                    raw=dict(raw_value),
                )
            )
        return parsed_sources

    @staticmethod
    def _is_allowed_public_http_url(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        host = parsed.hostname
        if not host:
            return False
        if host == "localhost" or host.endswith((".local", ".internal")):
            return False

        try:
            host_ip = ip_address(host)
        except ValueError:
            return True

        if (
            host_ip.is_private
            or host_ip.is_loopback
            or host_ip.is_link_local
            or host_ip.is_reserved
            or host_ip.is_multicast
        ):
            return False
        return True
