"""信息摄取（Ingest）单元测试。

测试覆盖：
- URL 去重逻辑（url_hash 计算）
- 抓取器配置验证
- 抓取结果处理
- IngestService 核心逻辑
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.modules.sources.application.ingest_service import IngestResult, IngestService
from src.modules.sources.domain.entities import Source, SourceType
from src.modules.sources.infrastructure.fetchers.base import (
    FetchedItem,
    FetchResult,
    FetchStatus,
)
from src.modules.sources.infrastructure.fetchers.factory import FetcherFactory
from src.modules.sources.infrastructure.fetchers.newsnow import NewsNowFetcher
from src.modules.sources.infrastructure.fetchers.rss import RSSFetcher
from src.modules.sources.infrastructure.fetchers.site import SiteFetcher
from src.modules.sources.infrastructure.models import IngestStatus

# 使用 anyio 作为异步测试后端
pytestmark = pytest.mark.anyio

# ============================================
# URL 去重测试
# ============================================


class TestUrlHash:
    """URL 哈希计算测试。"""

    def test_url_hash_consistency(self):
        """相同 URL 应产生相同的哈希。"""
        url = "https://example.com/article/123"
        hash1 = IngestService._compute_url_hash(url)
        hash2 = IngestService._compute_url_hash(url)
        assert hash1 == hash2

    def test_url_hash_case_insensitive(self):
        """URL 哈希应该不区分大小写。"""
        url1 = "https://Example.com/Article/123"
        url2 = "https://example.com/article/123"
        hash1 = IngestService._compute_url_hash(url1)
        hash2 = IngestService._compute_url_hash(url2)
        assert hash1 == hash2

    def test_url_hash_trailing_slash(self):
        """URL 哈希应该忽略尾部斜杠。"""
        url1 = "https://example.com/article/123"
        url2 = "https://example.com/article/123/"
        hash1 = IngestService._compute_url_hash(url1)
        hash2 = IngestService._compute_url_hash(url2)
        assert hash1 == hash2

    def test_url_hash_whitespace(self):
        """URL 哈希应该忽略前后空白。"""
        url1 = "  https://example.com/article/123  "
        url2 = "https://example.com/article/123"
        hash1 = IngestService._compute_url_hash(url1)
        hash2 = IngestService._compute_url_hash(url2)
        assert hash1 == hash2

    def test_url_hash_different_urls(self):
        """不同 URL 应产生不同的哈希。"""
        url1 = "https://example.com/article/123"
        url2 = "https://example.com/article/456"
        hash1 = IngestService._compute_url_hash(url1)
        hash2 = IngestService._compute_url_hash(url2)
        assert hash1 != hash2

    def test_url_hash_length(self):
        """URL 哈希长度应为 32 字符。"""
        url = "https://example.com/article/123"
        hash_value = IngestService._compute_url_hash(url)
        assert len(hash_value) == 32


# ============================================
# 抓取结果测试
# ============================================


class TestFetchResult:
    """FetchResult 测试。"""

    def test_success_result(self):
        """测试成功结果。"""
        items = [
            FetchedItem(url="https://example.com/1", title="Test 1"),
            FetchedItem(url="https://example.com/2", title="Test 2"),
        ]
        result = FetchResult.success(items, duration_ms=100)

        assert result.status == FetchStatus.SUCCESS
        assert result.is_success is True
        assert result.items_count == 2
        assert result.error_message is None

    def test_empty_success_result(self):
        """测试空结果（成功但无数据）。"""
        result = FetchResult.success([], duration_ms=50)

        assert result.status == FetchStatus.EMPTY
        assert result.is_success is True
        assert result.items_count == 0

    def test_failed_result(self):
        """测试失败结果。"""
        result = FetchResult.failed("Connection timeout", duration_ms=30000)

        assert result.status == FetchStatus.FAILED
        assert result.is_success is False
        assert result.items_count == 0
        assert result.error_message == "Connection timeout"

    def test_partial_result(self):
        """测试部分成功结果。"""
        items = [FetchedItem(url="https://example.com/1", title="Test 1")]
        result = FetchResult.partial(
            items, "Some items failed to parse", duration_ms=200
        )

        assert result.status == FetchStatus.PARTIAL
        assert result.is_success is True
        assert result.items_count == 1
        assert result.error_message == "Some items failed to parse"


# ============================================
# RSS 抓取器测试
# ============================================


class TestRSSFetcher:
    """RSS 抓取器测试。"""

    def test_validate_config_valid(self):
        """测试有效配置。"""
        fetcher = RSSFetcher(
            config={"feed_url": "https://example.com/feed.xml"},
            max_items=20,
        )
        valid, error = fetcher.validate_config()
        assert valid is True
        assert error is None

    def test_validate_config_missing_url(self):
        """测试缺少 URL 的配置。"""
        fetcher = RSSFetcher(config={}, max_items=20)
        valid, error = fetcher.validate_config()
        assert valid is False
        assert "feed_url" in error

    def test_validate_config_invalid_url(self):
        """测试无效 URL。"""
        fetcher = RSSFetcher(
            config={"feed_url": "not-a-valid-url"},
            max_items=20,
        )
        valid, error = fetcher.validate_config()
        assert valid is False
        assert "HTTP" in error

    def test_strip_html(self):
        """测试 HTML 标签移除。"""
        fetcher = RSSFetcher(config={"feed_url": "https://example.com"}, max_items=20)
        result = fetcher._strip_html("<p>Hello <b>World</b></p>")
        assert result == "Hello World"

    def test_strip_html_entities(self):
        """测试 HTML 实体处理。"""
        fetcher = RSSFetcher(config={"feed_url": "https://example.com"}, max_items=20)
        result = fetcher._strip_html("A &amp; B &lt; C")
        assert result == "A & B < C"


# ============================================
# NewsNow 抓取器测试
# ============================================


class TestNewsNowFetcher:
    """NewsNow 抓取器测试。"""

    def test_validate_config_valid(self):
        """测试有效配置。"""
        fetcher = NewsNowFetcher(
            config={
                "base_url": "https://www.newsnow.co.uk",
                "source_id": "Technology",
            },
            max_items=20,
        )
        valid, error = fetcher.validate_config()
        assert valid is True
        assert error is None

    def test_validate_config_with_category_path(self):
        """测试使用 category_path 的配置。"""
        fetcher = NewsNowFetcher(
            config={
                "base_url": "https://www.newsnow.co.uk",
                "category_path": "/h/Technology",
            },
            max_items=20,
        )
        valid, error = fetcher.validate_config()
        assert valid is True

    def test_validate_config_missing_base_url(self):
        """测试缺少 base_url。"""
        fetcher = NewsNowFetcher(
            config={"source_id": "Technology"},
            max_items=20,
        )
        valid, error = fetcher.validate_config()
        assert valid is False
        assert "base_url" in error

    def test_is_valid_news_url(self):
        """测试新闻 URL 验证。"""
        fetcher = NewsNowFetcher(
            config={"base_url": "https://example.com", "source_id": "test"},
            max_items=20,
        )

        assert (
            fetcher._is_valid_news_url("https://news.example.com/article/123") is True
        )
        assert fetcher._is_valid_news_url("/login") is False
        assert fetcher._is_valid_news_url("javascript:void(0)") is False
        assert fetcher._is_valid_news_url("mailto:test@example.com") is False

    def test_parse_relative_time(self):
        """测试相对时间解析。"""
        fetcher = NewsNowFetcher(
            config={"base_url": "https://example.com", "source_id": "test"},
            max_items=20,
        )

        result = fetcher._parse_relative_time("2 hours ago")
        assert result is not None
        assert (datetime.now(UTC) - result).total_seconds() < 3 * 3600

        result = fetcher._parse_relative_time("30 minutes ago")
        assert result is not None

        result = fetcher._parse_relative_time("invalid")
        assert result is None


# ============================================
# SITE 抓取器测试
# ============================================


class TestSiteFetcher:
    """SITE 抓取器测试。"""

    def test_validate_config_valid(self):
        """测试有效配置。"""
        fetcher = SiteFetcher(
            config={
                "list_url": "https://example.com/news",
                "selectors": {
                    "item": "article",
                    "title": "h2 a",
                    "link": "h2 a",
                },
            },
            max_items=20,
        )
        valid, error = fetcher.validate_config()
        assert valid is True
        assert error is None

    def test_validate_config_missing_selectors(self):
        """测试缺少选择器。"""
        fetcher = SiteFetcher(
            config={"list_url": "https://example.com/news"},
            max_items=20,
        )
        valid, error = fetcher.validate_config()
        assert valid is False
        assert "item" in error

    def test_parse_relative_time_chinese(self):
        """测试中文相对时间解析。"""
        fetcher = SiteFetcher(
            config={
                "list_url": "https://example.com",
                "selectors": {"item": "div", "title": "a"},
            },
            max_items=20,
        )

        result = fetcher._parse_relative_time("2小时前")
        assert result is not None

        result = fetcher._parse_relative_time("昨天")
        assert result is not None

        result = fetcher._parse_relative_time("刚刚")
        assert result is not None


# ============================================
# 抓取器工厂测试
# ============================================


class TestFetcherFactory:
    """抓取器工厂测试。"""

    def test_create_rss_fetcher(self):
        """测试创建 RSS 抓取器。"""
        fetcher = FetcherFactory.create(
            source_type=SourceType.RSS,
            config={"feed_url": "https://example.com/feed.xml"},
        )
        assert isinstance(fetcher, RSSFetcher)

    def test_create_newsnow_fetcher(self):
        """测试创建 NewsNow 抓取器。"""
        fetcher = FetcherFactory.create(
            source_type=SourceType.NEWSNOW,
            config={"base_url": "https://example.com", "source_id": "test"},
        )
        assert isinstance(fetcher, NewsNowFetcher)

    def test_create_site_fetcher(self):
        """测试创建 SITE 抓取器。"""
        fetcher = FetcherFactory.create(
            source_type=SourceType.SITE,
            config={
                "list_url": "https://example.com",
                "selectors": {"item": "div", "title": "a"},
            },
        )
        assert isinstance(fetcher, SiteFetcher)

    def test_get_default_interval(self):
        """测试获取默认抓取间隔。"""
        assert FetcherFactory.get_default_interval(SourceType.RSS) == 900  # 15 min
        assert FetcherFactory.get_default_interval(SourceType.NEWSNOW) == 1800  # 30 min


# ============================================
# IngestService 测试
# ============================================


class TestIngestService:
    """IngestService 测试。"""

    @pytest.fixture
    def mock_source_repo(self):
        """Mock 源仓储。"""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_item_repo(self):
        """Mock 条目仓储。"""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_event_bus(self):
        """Mock 事件总线。"""
        bus = AsyncMock()
        return bus

    @pytest.fixture
    def mock_fetcher_factory(self):
        """Mock 抓取器工厂。"""
        factory = AsyncMock()
        return factory

    @pytest.fixture
    def ingest_service(
        self, mock_source_repo, mock_item_repo, mock_event_bus, mock_fetcher_factory
    ):
        """创建 IngestService 实例。"""
        return IngestService(
            source_repository=mock_source_repo,
            item_repository=mock_item_repo,
            event_bus=mock_event_bus,
            fetcher_factory=mock_fetcher_factory,
        )

    @pytest.fixture
    def sample_source(self):
        """创建示例源。"""
        return Source(
            id="source-123",
            type=SourceType.RSS,
            name="Test RSS Feed",
            enabled=True,
            fetch_interval_sec=900,
            config={"feed_url": "https://example.com/feed.xml"},
        )

    async def test_dedupe_and_save_new_items(
        self, ingest_service, mock_item_repo, sample_source
    ):
        """测试去重并保存新条目（使用原子插入）。"""
        # 设置 mock：create_if_not_exists 返回创建的 item（表示成功创建）
        mock_item_repo.create_if_not_exists.side_effect = lambda item: item

        fetched_items = [
            FetchedItem(url="https://example.com/1", title="Article 1"),
            FetchedItem(url="https://example.com/2", title="Article 2"),
        ]

        new_items, duplicate_count = await ingest_service._dedupe_and_save(
            source=sample_source,
            fetched_items=fetched_items,
        )

        assert len(new_items) == 2
        assert duplicate_count == 0
        assert mock_item_repo.create_if_not_exists.call_count == 2

    async def test_dedupe_and_save_duplicate_items(
        self, ingest_service, mock_item_repo, sample_source
    ):
        """测试去重逻辑能正确识别重复条目（使用原子插入）。"""
        # 设置 mock：create_if_not_exists 返回 None（表示 url_hash 已存在）
        mock_item_repo.create_if_not_exists.return_value = None

        fetched_items = [
            FetchedItem(url="https://example.com/1", title="Article 1"),
            FetchedItem(url="https://example.com/2", title="Article 2"),
        ]

        new_items, duplicate_count = await ingest_service._dedupe_and_save(
            source=sample_source,
            fetched_items=fetched_items,
        )

        assert len(new_items) == 0
        assert duplicate_count == 2
        assert mock_item_repo.create_if_not_exists.call_count == 2

    async def test_dedupe_and_save_mixed(
        self, ingest_service, mock_item_repo, sample_source
    ):
        """测试混合情况（部分新、部分重复）。"""
        # 设置 mock：第一个成功创建，第二个已存在
        def create_if_not_exists_side_effect(item):
            if item.url == "https://example.com/new":
                return item
            return None  # 已存在

        mock_item_repo.create_if_not_exists.side_effect = (
            create_if_not_exists_side_effect
        )

        fetched_items = [
            FetchedItem(url="https://example.com/new", title="New Article"),
            FetchedItem(url="https://example.com/old", title="Old Article"),
        ]

        new_items, duplicate_count = await ingest_service._dedupe_and_save(
            source=sample_source,
            fetched_items=fetched_items,
        )

        assert len(new_items) == 1
        assert duplicate_count == 1
        assert new_items[0].url == "https://example.com/new"

    async def test_dedupe_and_save_atomic_prevents_race_condition(
        self, ingest_service, mock_item_repo, sample_source
    ):
        """测试原子插入能够防止竞态条件。

        模拟并发场景：多个相同 URL 同时尝试插入，
        只有第一个成功，其他都被识别为重复。
        """
        call_count = 0

        def create_if_not_exists_side_effect(item):
            nonlocal call_count
            call_count += 1
            # 只有第一次调用成功，模拟并发时只有一个成功
            if call_count == 1:
                return item
            return None

        mock_item_repo.create_if_not_exists.side_effect = (
            create_if_not_exists_side_effect
        )

        # 模拟三个相同 URL 的条目（可能来自并发抓取）
        fetched_items = [
            FetchedItem(url="https://example.com/same", title="Article 1"),
            FetchedItem(url="https://example.com/same", title="Article 1"),
            FetchedItem(url="https://example.com/same", title="Article 1"),
        ]

        new_items, duplicate_count = await ingest_service._dedupe_and_save(
            source=sample_source,
            fetched_items=fetched_items,
        )

        # 只应该有 1 个新条目，2 个重复
        assert len(new_items) == 1
        assert duplicate_count == 2

    async def test_ingest_source_by_id_not_found(
        self, ingest_service, mock_source_repo
    ):
        """测试抓取不存在的源。"""
        mock_source_repo.get_by_id.return_value = None

        result = await ingest_service.ingest_source_by_id("non-existent")

        assert result.is_success is False
        assert "not found" in result.error_message

    async def test_ingest_source_by_id_disabled(
        self, ingest_service, mock_source_repo, sample_source
    ):
        """测试抓取已禁用的源。"""
        sample_source.enabled = False
        mock_source_repo.get_by_id.return_value = sample_source

        result = await ingest_service.ingest_source_by_id(sample_source.id)

        assert result.is_success is False
        assert "disabled" in result.error_message


# ============================================
# IngestResult 测试
# ============================================


class TestIngestResult:
    """IngestResult 测试。"""

    def test_success_result(self):
        """测试成功结果。"""
        result = IngestResult(
            source_id="source-123",
            status=IngestStatus.SUCCESS,
            items_fetched=10,
            items_new=5,
            items_duplicate=5,
            duration_ms=1000,
            new_item_ids=["item-1", "item-2"],
        )

        assert result.is_success is True
        assert result.items_new == 5

    def test_failed_result(self):
        """测试失败结果。"""
        result = IngestResult(
            source_id="source-123",
            status=IngestStatus.FAILED,
            error_message="Connection timeout",
        )

        assert result.is_success is False
        assert result.error_message == "Connection timeout"

    def test_partial_result(self):
        """测试部分成功结果。"""
        result = IngestResult(
            source_id="source-123",
            status=IngestStatus.PARTIAL,
            items_fetched=10,
            items_new=3,
            error_message="Some parsing errors",
        )

        assert result.is_success is True


# ============================================
# Redis 锁测试
# ============================================


class TestRedisIngestLock:
    """Redis Ingest 锁测试。"""

    def test_ingest_lock_key_format(self):
        """测试 Ingest 锁 key 格式。"""
        from src.core.infrastructure.redis.keys import RedisKeys

        key = RedisKeys.ingest_lock("source-123")
        assert key == "lock:ingest:source-123"

    def test_ingest_lock_key_unique_per_source(self):
        """测试不同 Source 产生不同的锁 key。"""
        from src.core.infrastructure.redis.keys import RedisKeys

        key1 = RedisKeys.ingest_lock("source-123")
        key2 = RedisKeys.ingest_lock("source-456")
        assert key1 != key2


# ============================================
# 调度更新测试
# ============================================


class TestSchedulerNextFetchUpdate:
    """测试调度时更新 next_fetch_at。"""

    def test_source_schedule_next_fetch(self):
        """测试 Source 的 next_fetch 调度逻辑。"""
        source = Source(
            id="source-123",
            type=SourceType.RSS,
            name="Test Source",
            enabled=True,
            fetch_interval_sec=900,  # 15 分钟
            config={"feed_url": "https://example.com/feed.xml"},
        )

        # 初始状态 next_fetch_at 应为 None
        assert source.next_fetch_at is None

        # 模拟 mark_fetch_success
        source.mark_fetch_success(items_count=5)

        # next_fetch_at 应该被设置为未来时间
        assert source.next_fetch_at is not None
        time_diff = (source.next_fetch_at - datetime.now()).total_seconds()
        # 应该在 15 分钟左右（允许一些误差）
        assert 890 < time_diff < 910

    def test_source_schedule_with_backoff(self):
        """测试错误退避调度逻辑。"""
        source = Source(
            id="source-123",
            type=SourceType.RSS,
            name="Test Source",
            enabled=True,
            fetch_interval_sec=900,
            config={"feed_url": "https://example.com/feed.xml"},
        )

        # 模拟连续错误
        source.mark_fetch_error()
        assert source.error_streak == 1

        # 第一次错误：退避 = 2^1 * 900 = 1800 秒
        first_next_fetch = source.next_fetch_at

        source.mark_fetch_error()
        assert source.error_streak == 2

        # 第二次错误：退避 = 2^2 * 900 = 3600 秒
        second_next_fetch = source.next_fetch_at

        # 第二次退避应该比第一次长
        assert second_next_fetch > first_next_fetch
