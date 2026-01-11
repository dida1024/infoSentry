"""NewsNow 抓取器实现。

NewsNow 是一个新闻聚合网站，提供多个领域的新闻源。
抓取策略：解析 NewsNow 的列表页面，提取新闻条目。
"""

import re
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin

import httpx
from loguru import logger

from src.modules.sources.infrastructure.fetchers.base import (
    BaseFetcher,
    FetchedItem,
    FetchResult,
)


class NewsNowFetcher(BaseFetcher):
    """NewsNow 抓取器。

    配置格式：
    {
        "base_url": "https://www.newsnow.co.uk",
        "source_id": "Technology",  # NewsNow 的分类 ID
        "category_path": "/h/Technology"  # 分类路径
    }
    """

    # 请求超时设置
    TIMEOUT = 30.0

    # 默认 User-Agent
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def validate_config(self) -> tuple[bool, str | None]:
        """验证配置。"""
        if not self.config.get("base_url"):
            return False, "Missing base_url in config"
        if not self.config.get("source_id") and not self.config.get("category_path"):
            return False, "Missing source_id or category_path in config"
        return True, None

    async def fetch(self) -> FetchResult:
        """执行抓取。"""
        start_time = time.time()

        valid, error = self.validate_config()
        if not valid:
            return FetchResult.failed(error or "Invalid config")

        try:
            items = await self._fetch_items()
            duration_ms = int((time.time() - start_time) * 1000)

            return FetchResult.success(
                items=items[: self.max_items],
                duration_ms=duration_ms,
                metadata={
                    "source_id": self.config.get("source_id"),
                    "total_found": len(items),
                },
            )
        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"NewsNow fetch timeout: {e}")
            return FetchResult.failed(
                f"Timeout: {str(e)}",
                duration_ms=duration_ms,
            )
        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"NewsNow fetch HTTP error: {e.response.status_code}")
            return FetchResult.failed(
                f"HTTP {e.response.status_code}: {str(e)}",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"NewsNow fetch error: {e}")
            return FetchResult.failed(
                f"Error: {str(e)}",
                duration_ms=duration_ms,
            )

    async def _fetch_items(self) -> list[FetchedItem]:
        """实际抓取逻辑。"""
        base_url = self.config["base_url"]
        category_path = self.config.get("category_path", "")

        # 如果没有 category_path，从 source_id 构建
        if not category_path and self.config.get("source_id"):
            category_path = f"/h/{self.config['source_id']}"

        url = urljoin(base_url, category_path)

        async with httpx.AsyncClient(
            timeout=self.TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": self.USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
            )
            response.raise_for_status()

            return self._parse_html(response.text, base_url)

    def _parse_html(self, html: str, base_url: str) -> list[FetchedItem]:
        """解析 HTML 内容提取新闻条目。

        NewsNow 的页面结构可能会变化，这里使用正则和简单解析。
        生产环境建议使用 BeautifulSoup 或 lxml。
        """
        items: list[FetchedItem] = []

        try:
            # 尝试使用 BeautifulSoup 解析（如果可用）
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")

            # NewsNow 的新闻条目通常在 .hl 或类似的类中
            # 这是一个简化的解析逻辑，实际需要根据真实页面结构调整
            for article in soup.select("div.hl, article, .news-item, .headline"):
                try:
                    # 查找链接
                    link_elem = article.select_one("a[href]")
                    if not link_elem:
                        continue

                    url = link_elem.get("href", "")
                    if not url:
                        continue

                    # 处理相对路径
                    if url.startswith("/"):
                        url = urljoin(base_url, url)

                    # 跳过非新闻链接
                    if not self._is_valid_news_url(url):
                        continue

                    # 提取标题
                    title = self._clean_title(link_elem.get_text())
                    if not title:
                        continue

                    # 提取摘要（如果有）
                    snippet_elem = article.select_one(".snippet, .summary, .excerpt, p")
                    snippet = None
                    if snippet_elem and snippet_elem != link_elem:
                        snippet = self._truncate_snippet(snippet_elem.get_text())

                    # 提取发布时间（如果有）
                    time_elem = article.select_one("time, .time, .date, [datetime]")
                    published_at = None
                    if time_elem:
                        published_at = self._parse_time(
                            time_elem.get("datetime") or time_elem.get_text()
                        )

                    items.append(
                        FetchedItem(
                            url=url,
                            title=title,
                            snippet=snippet,
                            published_at=published_at,
                            raw_data={"source": "newsnow"},
                        )
                    )
                except Exception as e:
                    logger.debug(f"Failed to parse article: {e}")
                    continue

        except ImportError:
            # 如果没有 BeautifulSoup，使用正则表达式
            logger.warning("BeautifulSoup not available, using regex parsing")
            items = self._parse_with_regex(html, base_url)

        return items

    def _parse_with_regex(self, html: str, base_url: str) -> list[FetchedItem]:
        """使用正则表达式解析（备用方案）。"""
        items: list[FetchedItem] = []

        # 简单的正则匹配链接和标题
        pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.IGNORECASE)

        for url, title in matches:
            if not url or not title:
                continue

            # 处理相对路径
            if url.startswith("/"):
                url = urljoin(base_url, url)

            # 过滤
            if not self._is_valid_news_url(url):
                continue

            title = self._clean_title(title)
            if not title or len(title) < 10:
                continue

            items.append(
                FetchedItem(
                    url=url,
                    title=title,
                    snippet=None,
                    published_at=None,
                    raw_data={"source": "newsnow", "parsed_with": "regex"},
                )
            )

        return items

    def _is_valid_news_url(self, url: str) -> bool:
        """检查是否是有效的新闻 URL。"""
        if not url:
            return False

        # 跳过 NewsNow 内部链接
        if "newsnow.co.uk" in url and not url.startswith("http"):
            return False

        # 跳过常见的非新闻链接
        skip_patterns = [
            "/login",
            "/register",
            "/about",
            "/contact",
            "/privacy",
            "/terms",
            "/advertise",
            "/help",
            "javascript:",
            "mailto:",
            "#",
        ]
        for pattern in skip_patterns:
            if pattern in url.lower():
                return False

        return True

    def _parse_time(self, time_str: str | None) -> datetime | None:
        """解析时间字符串。"""
        if not time_str:
            return None

        try:
            # ISO 格式
            if "T" in time_str:
                return datetime.fromisoformat(time_str.replace("Z", "+00:00"))

            # 相对时间格式（如 "2 hours ago"）
            time_str = time_str.lower().strip()
            if "ago" in time_str:
                return self._parse_relative_time(time_str)

            # 其他格式尝试
            for fmt in [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%d %b %Y",
                "%B %d, %Y",
            ]:
                try:
                    return datetime.strptime(time_str, fmt).replace(tzinfo=UTC)
                except ValueError:
                    continue

        except Exception:
            pass

        return None

    def _parse_relative_time(self, time_str: str) -> datetime | None:
        """解析相对时间（如 "2 hours ago"）。"""
        now = datetime.now(UTC)

        # 匹配数字和单位
        match = re.search(
            r"(\d+)\s*(second|minute|hour|day|week|month)s?\s*ago", time_str
        )
        if not match:
            return None

        value = int(match.group(1))
        unit = match.group(2)

        deltas = {
            "second": timedelta(seconds=value),
            "minute": timedelta(minutes=value),
            "hour": timedelta(hours=value),
            "day": timedelta(days=value),
            "week": timedelta(weeks=value),
            "month": timedelta(days=value * 30),
        }

        delta = deltas.get(unit)
        if delta:
            return now - delta

        return None
