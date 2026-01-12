"""RSS 抓取器实现。

支持标准的 RSS 2.0 和 Atom 格式。
"""

import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from loguru import logger

from src.modules.sources.infrastructure.fetchers.base import (
    BaseFetcher,
    FetchedItem,
    FetchResult,
)


class RSSFetcher(BaseFetcher):
    """RSS 抓取器。

    配置格式：
    {
        "feed_url": "https://example.com/feed.xml"
    }
    """

    TIMEOUT = 30.0

    USER_AGENT = "Mozilla/5.0 (compatible; InfoSentry/1.0; +https://infosentry.app)"

    def validate_config(self) -> tuple[bool, str | None]:
        """验证配置。"""
        feed_url = self.config.get("feed_url")
        if not feed_url:
            return False, "Missing feed_url in config"
        if not feed_url.startswith(("http://", "https://")):
            return False, "feed_url must be a valid HTTP(S) URL"
        return True, None

    async def fetch(self) -> FetchResult:
        """执行抓取。"""
        start_time = time.time()

        valid, error = self.validate_config()
        if not valid:
            return FetchResult.failed(error or "Invalid config")

        feed_url = self.config["feed_url"]

        try:
            async with httpx.AsyncClient(
                timeout=self.TIMEOUT,
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    feed_url,
                    headers={
                        "User-Agent": self.USER_AGENT,
                        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
                    },
                )
                response.raise_for_status()

                items = self._parse_feed(response.text)
                duration_ms = int((time.time() - start_time) * 1000)

                return FetchResult.success(
                    items=items[: self.max_items],
                    duration_ms=duration_ms,
                    metadata={
                        "feed_url": feed_url,
                        "total_found": len(items),
                        "content_type": response.headers.get("content-type", ""),
                    },
                )

        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"RSS fetch timeout for {feed_url}: {e}")
            return FetchResult.failed(
                f"Timeout: {str(e)}",
                duration_ms=duration_ms,
            )
        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                f"RSS fetch HTTP error for {feed_url}: {e.response.status_code}"
            )
            return FetchResult.failed(
                f"HTTP {e.response.status_code}",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"RSS fetch error for {feed_url}: {e}")
            return FetchResult.failed(
                f"Error: {str(e)}",
                duration_ms=duration_ms,
            )

    def _parse_feed(self, content: str) -> list[FetchedItem]:
        """解析 RSS/Atom 内容。"""
        items: list[FetchedItem] = []

        try:
            # 尝试使用 feedparser（如果可用）
            import feedparser

            feed = feedparser.parse(content)

            for entry in feed.entries:
                try:
                    # 获取 URL
                    url = entry.get("link", "")
                    if not url:
                        # Atom 格式可能有多个 link
                        links = entry.get("links", [])
                        for link in links:
                            if link.get("rel") in ("alternate", None):
                                url = link.get("href", "")
                                break

                    if not url:
                        continue

                    # 获取标题
                    title = self._clean_title(entry.get("title", ""))
                    if not title:
                        continue

                    # 获取摘要
                    snippet = None
                    summary = entry.get("summary") or entry.get("description", "")
                    if summary:
                        # 移除 HTML 标签
                        snippet = self._strip_html(summary)
                        snippet = self._truncate_snippet(snippet)

                    # 获取发布时间
                    published_at = self._parse_feed_date(entry)

                    items.append(
                        FetchedItem(
                            url=url,
                            title=title,
                            snippet=snippet,
                            published_at=published_at,
                            raw_data={
                                "source": "rss",
                                "author": entry.get("author"),
                                "tags": [t.get("term") for t in entry.get("tags", [])],
                            },
                        )
                    )
                except Exception as e:
                    logger.debug(f"Failed to parse RSS entry: {e}")
                    continue

        except ImportError:
            # 如果没有 feedparser，使用简单的 XML 解析
            logger.warning("feedparser not available, using basic XML parsing")
            items = self._parse_xml_basic(content)

        return items

    def _parse_xml_basic(self, content: str) -> list[FetchedItem]:
        """基本的 XML 解析（不依赖 feedparser）。"""
        import xml.etree.ElementTree as ET

        items: list[FetchedItem] = []

        try:
            root = ET.fromstring(content)

            # 检测是 RSS 还是 Atom
            is_atom = (
                "atom" in root.tag.lower()
                or root.tag == "{http://www.w3.org/2005/Atom}feed"
            )

            if is_atom:
                items = self._parse_atom_basic(root)
            else:
                items = self._parse_rss_basic(root)

        except ET.ParseError as e:
            logger.warning(f"XML parse error: {e}")

        return items

    def _parse_rss_basic(self, root) -> list[FetchedItem]:
        """解析 RSS 2.0 格式。"""

        items: list[FetchedItem] = []

        # RSS 2.0 结构: rss/channel/item
        channel = root.find("channel")
        if channel is None:
            return items

        for item in channel.findall("item"):
            try:
                link = item.findtext("link", "")
                title = self._clean_title(item.findtext("title", ""))

                if not link or not title:
                    continue

                description = item.findtext("description", "")
                snippet = (
                    self._truncate_snippet(self._strip_html(description))
                    if description
                    else None
                )

                pub_date = item.findtext("pubDate")
                published_at = self._parse_rfc2822_date(pub_date) if pub_date else None

                items.append(
                    FetchedItem(
                        url=link,
                        title=title,
                        snippet=snippet,
                        published_at=published_at,
                        raw_data={"source": "rss", "parsed_with": "xml_basic"},
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to parse RSS item: {e}")
                continue

        return items

    def _parse_atom_basic(self, root) -> list[FetchedItem]:
        """解析 Atom 格式。"""
        items: list[FetchedItem] = []

        # Atom 命名空间
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall("atom:entry", ns) or root.findall("entry"):
            try:
                # 获取链接
                link = ""
                for link_elem in entry.findall("atom:link", ns) or entry.findall(
                    "link"
                ):
                    rel = link_elem.get("rel", "alternate")
                    if rel in ("alternate", None):
                        link = link_elem.get("href", "")
                        break

                # 获取标题
                title_elem = entry.find("atom:title", ns) or entry.find("title")
                title = self._clean_title(
                    title_elem.text if title_elem is not None else ""
                )

                if not link or not title:
                    continue

                # 获取摘要
                summary_elem = entry.find("atom:summary", ns) or entry.find("summary")
                snippet = None
                if summary_elem is not None and summary_elem.text:
                    snippet = self._truncate_snippet(
                        self._strip_html(summary_elem.text)
                    )

                # 获取发布时间
                published_elem = entry.find("atom:published", ns) or entry.find(
                    "published"
                )
                updated_elem = entry.find("atom:updated", ns) or entry.find("updated")
                date_str = (
                    published_elem.text if published_elem is not None else None
                ) or (updated_elem.text if updated_elem is not None else None)
                published_at = self._parse_iso_date(date_str) if date_str else None

                items.append(
                    FetchedItem(
                        url=link,
                        title=title,
                        snippet=snippet,
                        published_at=published_at,
                        raw_data={"source": "atom", "parsed_with": "xml_basic"},
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to parse Atom entry: {e}")
                continue

        return items

    def _parse_feed_date(self, entry: Any) -> datetime | None:
        """从 feedparser entry 解析日期。"""
        # feedparser 会将日期解析为 struct_time
        for field in ("published_parsed", "updated_parsed", "created_parsed"):
            parsed = getattr(entry, field, None)
            if parsed:
                try:
                    return datetime(*parsed[:6], tzinfo=UTC)
                except Exception as e:
                    logger.debug(f"Failed to parse {field}: {e}")

        # 尝试原始字符串
        for field in ("published", "updated", "created"):
            date_str = getattr(entry, field, None)
            if date_str:
                parsed = self._parse_rfc2822_date(date_str) or self._parse_iso_date(
                    date_str
                )
                if parsed:
                    return parsed

        return None

    def _parse_rfc2822_date(self, date_str: str) -> datetime | None:
        """解析 RFC 2822 日期格式。"""
        try:
            return parsedate_to_datetime(date_str)
        except Exception as e:
            logger.debug(f"Failed to parse RFC 2822 date '{date_str}': {e}")
            return None

    def _parse_iso_date(self, date_str: str) -> datetime | None:
        """解析 ISO 8601 日期格式。"""
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception as e:
            logger.debug(f"Failed to parse ISO date '{date_str}': {e}")
            return None

    def _strip_html(self, text: str) -> str:
        """移除 HTML 标签。"""
        import re

        # 移除 HTML 标签
        text = re.sub(r"<[^>]+>", "", text)
        # 处理 HTML 实体
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
        # 移除多余空白
        text = " ".join(text.split())
        return text.strip()
