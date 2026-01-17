"""SITE/list-only 抓取器实现。

使用 CSS 选择器解析网站列表页面，提取新闻条目。
v0 只支持列表页抓取，不抓详情页。
"""

import re
import time
from datetime import UTC, datetime
from urllib.parse import urljoin

import httpx
from loguru import logger

from src.modules.sources.infrastructure.fetchers.base import (
    BaseFetcher,
    FetchedItem,
    FetchResult,
)


class SiteFetcher(BaseFetcher):
    """SITE 抓取器。

    配置格式：
    {
        "list_url": "https://example.com/news",
        "selectors": {
            "item": "article.news-item",      # 条目容器选择器
            "title": "h2 a",                   # 标题选择器（相对于 item）
            "link": "h2 a",                    # 链接选择器（相对于 item）
            "snippet": "p.summary",            # 摘要选择器（可选）
            "time": "time"                     # 时间选择器（可选）
        },
        "headers": {                           # 可选的额外请求头
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
    }
    """

    TIMEOUT = 30.0

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def validate_config(self) -> tuple[bool, str | None]:
        """验证配置。"""
        list_url = self.config.get("list_url")
        if not list_url:
            return False, "Missing list_url in config"
        if not self._is_allowed_url(list_url):
            return False, "list_url must be a public HTTP(S) URL"

        selectors = self.config.get("selectors", {})
        if not selectors.get("item"):
            return False, "Missing selectors.item in config"
        if not selectors.get("title") and not selectors.get("link"):
            return False, "Missing selectors.title or selectors.link in config"

        return True, None

    async def fetch(self) -> FetchResult:
        """执行抓取。"""
        start_time = time.time()

        valid, error = self.validate_config()
        if not valid:
            return FetchResult.failed(error or "Invalid config")

        list_url = self.config["list_url"]
        extra_headers = self.config.get("headers", {})

        try:
            async with httpx.AsyncClient(
                timeout=self.TIMEOUT,
                follow_redirects=True,
            ) as client:
                headers = {
                    "User-Agent": self.USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    **extra_headers,
                }

                response = await client.get(list_url, headers=headers)
                response.raise_for_status()

                items = self._parse_html(response.text, list_url)
                duration_ms = int((time.time() - start_time) * 1000)

                return FetchResult.success(
                    items=items[: self.max_items],
                    duration_ms=duration_ms,
                    metadata={
                        "list_url": list_url,
                        "total_found": len(items),
                    },
                )

        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"Site fetch timeout for {list_url}: {e}")
            return FetchResult.failed(
                f"Timeout: {str(e)}",
                duration_ms=duration_ms,
            )
        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                f"Site fetch HTTP error for {list_url}: {e.response.status_code}"
            )
            return FetchResult.failed(
                f"HTTP {e.response.status_code}",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"Site fetch error for {list_url}: {e}")
            return FetchResult.failed(
                f"Error: {str(e)}",
                duration_ms=duration_ms,
            )

    def _parse_html(self, html: str, base_url: str) -> list[FetchedItem]:
        """使用选择器解析 HTML。"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("BeautifulSoup is required for SITE fetcher")
            return []

        items: list[FetchedItem] = []
        selectors = self.config.get("selectors", {})

        soup = BeautifulSoup(html, "html.parser")

        # 查找所有条目容器
        item_selector = selectors.get("item", "article")
        containers = soup.select(item_selector)

        for container in containers:
            try:
                item = self._extract_item(container, selectors, base_url)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug(f"Failed to extract item: {e}")
                continue

        return items

    def _extract_item(
        self,
        container,
        selectors: dict[str, str],
        base_url: str,
    ) -> FetchedItem | None:
        """从容器元素中提取条目信息。"""
        # 提取链接
        link_selector = selectors.get("link") or selectors.get("title", "a")
        link_elem = container.select_one(link_selector)

        url = None
        if link_elem:
            url = link_elem.get("href", "")
            if url and not url.startswith(("http://", "https://")):
                url = urljoin(base_url, url)

        if not url:
            return None
        if not self._is_allowed_url(url):
            return None

        # 提取标题
        title_selector = selectors.get("title") or selectors.get("link", "a")
        title_elem = container.select_one(title_selector)
        title = self._clean_title(title_elem.get_text() if title_elem else "")

        if not title:
            return None

        # 提取摘要（可选）
        snippet = None
        snippet_selector = selectors.get("snippet")
        if snippet_selector:
            snippet_elem = container.select_one(snippet_selector)
            if snippet_elem:
                snippet = self._truncate_snippet(
                    self._strip_html(snippet_elem.get_text())
                )

        # 提取发布时间（可选）
        published_at = None
        time_selector = selectors.get("time")
        if time_selector:
            time_elem = container.select_one(time_selector)
            if time_elem:
                # 优先使用 datetime 属性
                datetime_attr = time_elem.get("datetime")
                if datetime_attr:
                    published_at = self._parse_datetime(datetime_attr)
                else:
                    published_at = self._parse_datetime(time_elem.get_text())

        return FetchedItem(
            url=url,
            title=title,
            snippet=snippet,
            published_at=published_at,
            raw_data={"source": "site"},
        )

    def _parse_datetime(self, date_str: str | None) -> datetime | None:
        """解析日期时间字符串。"""
        if not date_str:
            return None

        date_str = date_str.strip()

        # ISO 格式
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            pass

        # 常见格式
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y/%m/%d",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
            "%d %b %Y",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.replace(tzinfo=UTC)
            except ValueError:
                continue

        # 相对时间
        return self._parse_relative_time(date_str)

    def _parse_relative_time(self, text: str) -> datetime | None:
        """解析相对时间表达式。"""
        from datetime import timedelta

        text = text.lower().strip()
        now = datetime.now(UTC)

        # 中文相对时间
        cn_patterns = [
            (r"(\d+)\s*秒前", "seconds"),
            (r"(\d+)\s*分钟前", "minutes"),
            (r"(\d+)\s*小时前", "hours"),
            (r"(\d+)\s*天前", "days"),
            (r"(\d+)\s*周前", "weeks"),
            (r"刚刚", "now"),
            (r"今天", "today"),
            (r"昨天", "yesterday"),
        ]

        # 英文相对时间
        en_patterns = [
            (r"(\d+)\s*seconds?\s*ago", "seconds"),
            (r"(\d+)\s*minutes?\s*ago", "minutes"),
            (r"(\d+)\s*hours?\s*ago", "hours"),
            (r"(\d+)\s*days?\s*ago", "days"),
            (r"(\d+)\s*weeks?\s*ago", "weeks"),
            (r"just\s*now", "now"),
            (r"today", "today"),
            (r"yesterday", "yesterday"),
        ]

        for pattern, unit in cn_patterns + en_patterns:
            match = re.search(pattern, text)
            if match:
                if unit == "now":
                    return now
                elif unit == "today":
                    return now.replace(hour=0, minute=0, second=0, microsecond=0)
                elif unit == "yesterday":
                    return (now - timedelta(days=1)).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                else:
                    value = int(match.group(1))
                    delta_map = {
                        "seconds": timedelta(seconds=value),
                        "minutes": timedelta(minutes=value),
                        "hours": timedelta(hours=value),
                        "days": timedelta(days=value),
                        "weeks": timedelta(weeks=value),
                    }
                    return now - delta_map.get(unit, timedelta())

        return None

    def _strip_html(self, text: str) -> str:
        """移除 HTML 标签。"""
        # 移除 HTML 标签
        text = re.sub(r"<[^>]+>", "", text)
        # 处理常见 HTML 实体
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        # 移除多余空白
        text = " ".join(text.split())
        return text.strip()
