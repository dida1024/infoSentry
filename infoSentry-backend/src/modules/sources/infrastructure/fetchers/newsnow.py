"""NewsNow API fetcher implementation."""

from __future__ import annotations

import math
import re
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from loguru import logger

from src.core.config import settings
from src.modules.sources.infrastructure.fetchers.base import (
    BaseFetcher,
    FetchedItem,
    FetchResult,
)


class NewsNowFetcher(BaseFetcher):
    """Fetch items from NewsNow API endpoint."""

    def validate_config(self) -> tuple[bool, str | None]:
        source_id = self.config.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            return False, "Missing source_id in config"

        base_url = self._get_base_url()
        if not self._is_allowed_url(base_url):
            return False, "base_url must be a public HTTP(S) URL"

        api_path = self._get_api_path()
        if not api_path.startswith("/"):
            return False, "api_path must start with '/'"
        return True, None

    async def fetch(self) -> FetchResult:
        start_time = time.time()
        valid, error = self.validate_config()
        if not valid:
            return FetchResult.failed(error or "Invalid config")

        source_id = str(self.config["source_id"]).strip()
        api_url = f"{self._get_base_url().rstrip('/')}{self._get_api_path()}"
        latest_flag = "1" if self._get_latest_flag() else "0"

        try:
            async with httpx.AsyncClient(
                timeout=settings.FETCHER_TIMEOUT_SEC,
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    api_url,
                    params={"id": source_id, "latest": latest_flag},
                    headers={
                        "User-Agent": settings.FETCHER_USER_AGENT,
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                payload = response.json()

            items = self._parse_payload(payload)
            duration_ms = int((time.time() - start_time) * 1000)
            return FetchResult.success(
                items=items[: self.max_items],
                duration_ms=duration_ms,
                metadata={
                    "source_id": source_id,
                    "api_url": api_url,
                    "latest": latest_flag == "1",
                    "total_found": len(items),
                },
            )
        except httpx.TimeoutException as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"NewsNow fetch timeout for {source_id}: {exc}")
            return FetchResult.failed(
                f"Timeout: {str(exc)}",
                duration_ms=duration_ms,
            )
        except httpx.HTTPStatusError as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                f"NewsNow fetch HTTP error for {source_id}: {exc.response.status_code}"
            )
            return FetchResult.failed(
                f"HTTP {exc.response.status_code}",
                duration_ms=duration_ms,
            )
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"NewsNow fetch error for {source_id}: {exc}")
            return FetchResult.failed(
                f"Error: {str(exc)}",
                duration_ms=duration_ms,
            )

    def _parse_payload(self, payload: Any) -> list[FetchedItem]:
        if not isinstance(payload, dict):
            raise ValueError("NewsNow response payload must be an object")

        status = payload.get("status")
        if status not in ("success", "cache"):
            message = payload.get("message")
            if isinstance(message, str) and message:
                raise ValueError(f"NewsNow API error: {message}")
            raise ValueError("NewsNow API returned non-success status")

        items_raw = payload.get("items")
        if not isinstance(items_raw, list):
            raise ValueError("NewsNow API response missing items list")

        parsed_items: list[FetchedItem] = []
        seen_urls: set[str] = set()
        for raw_item in items_raw:
            if not isinstance(raw_item, dict):
                continue

            url_value = raw_item.get("url")
            title_value = raw_item.get("title")
            if not isinstance(url_value, str) or not isinstance(title_value, str):
                continue

            url = url_value.strip()
            if not url or not self._is_allowed_url(url):
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = self._clean_text(title_value)
            if not title:
                continue

            snippet = self._extract_snippet(raw_item.get("extra"))
            published_at = self._extract_published_at(raw_item)

            parsed_items.append(
                FetchedItem(
                    url=url,
                    title=title,
                    snippet=snippet,
                    published_at=published_at,
                    raw_data={
                        "source": "newsnow",
                        "id": raw_item.get("id"),
                        "status": status,
                    },
                )
            )
        return parsed_items

    def _extract_snippet(self, extra_value: object) -> str | None:
        if not isinstance(extra_value, dict):
            return None
        hover = extra_value.get("hover")
        if not isinstance(hover, str):
            return None
        cleaned = self._clean_text(hover)
        if not cleaned:
            return None
        if len(cleaned) <= 500:
            return cleaned
        return f"{cleaned[:497]}..."

    @staticmethod
    def _clean_text(value: str) -> str:
        cleaned = re.sub(r"<[^>]+>", "", value)
        return " ".join(cleaned.split())

    def _extract_published_at(self, item: dict[str, Any]) -> datetime | None:
        pub_date = item.get("pubDate")
        if pub_date is not None:
            parsed = self._parse_datetime_value(pub_date)
            if parsed is not None:
                return parsed

        extra = item.get("extra")
        if isinstance(extra, dict):
            return self._parse_datetime_value(extra.get("date"))
        return None

    @staticmethod
    def _parse_datetime_value(value: object) -> datetime | None:
        if value is None:
            return None

        if isinstance(value, (int, float)):
            if not math.isfinite(value):
                return None
            timestamp = float(value)
            if timestamp > 1_000_000_000_000:
                timestamp /= 1000.0
            if timestamp <= 0:
                return None
            return datetime.fromtimestamp(timestamp, tz=UTC)

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None

            if text.isdigit():
                try:
                    return NewsNowFetcher._parse_datetime_value(int(text))
                except ValueError:
                    return None

            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=UTC)
                return parsed
            except ValueError:
                return None

        return None

    def _get_base_url(self) -> str:
        base_url = self.config.get("base_url", settings.NEWSNOW_API_BASE_URL)
        return str(base_url).strip()

    def _get_api_path(self) -> str:
        api_path = self.config.get("api_path", settings.NEWSNOW_API_PATH)
        path = str(api_path).strip()
        return path or settings.NEWSNOW_API_PATH

    def _get_latest_flag(self) -> bool:
        value = self.config.get("latest", False)
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized in {"1", "true", "yes", "y", "on"}
        return False
