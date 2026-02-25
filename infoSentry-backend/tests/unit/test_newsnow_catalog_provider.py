"""Tests for NewsNow catalog provider."""

from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from src.modules.sources.infrastructure.newsnow_catalog_provider import (
    InfrastructureNewsNowCatalogProvider,
)

pytestmark = pytest.mark.anyio


def _write_snapshot(path: Path) -> None:
    path.write_text(
        """{
  "github": {"name": "Github", "interval": 600000},
  "v2ex": {"name": "V2EX", "title": "最新分享", "disable": true},
  "v2ex-share": {"name": "V2EX", "title": "最新分享", "disable": "cf"}
}""",
        encoding="utf-8",
    )


async def test_load_catalog_fallback_to_snapshot(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "sources.json"
    _write_snapshot(snapshot_path)

    provider = InfrastructureNewsNowCatalogProvider(
        catalog_url="https://example.com/sources.json",
        snapshot_path=snapshot_path,
    )
    provider._load_catalog_from_remote = AsyncMock(
        side_effect=httpx.ConnectError("network error")
    )

    catalog = await provider.load_catalog()
    assert catalog.loaded_from == "snapshot"
    assert len(catalog.sources) == 3
    assert catalog.sources[0].source_id == "github"
    assert catalog.sources[1].disable is True
    assert catalog.sources[2].disable is False


def test_parse_catalog_payload_type_error() -> None:
    with pytest.raises(ValueError, match="must be a JSON object"):
        InfrastructureNewsNowCatalogProvider._parse_catalog_payload([])
