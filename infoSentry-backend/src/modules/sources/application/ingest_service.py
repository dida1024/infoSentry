"""信息摄取服务。

协调抓取、去重、入库、事件发布等流程。
"""

import hashlib
import time
from datetime import UTC, datetime

from loguru import logger

from src.core.config import settings
from src.core.domain.events import EventBus
from src.modules.items.domain.entities import EmbeddingStatus, Item
from src.modules.items.domain.events import ItemIngestedEvent
from src.modules.items.domain.repository import ItemRepository
from src.modules.sources.domain.entities import Source
from src.modules.sources.domain.events import (
    SourceFetchErrorEvent,
    SourceFetchSuccessEvent,
)
from src.modules.sources.domain.repository import SourceRepository
from src.modules.sources.infrastructure.fetchers import (
    FetchedItem,
    FetcherFactory,
)
from src.modules.sources.infrastructure.models import IngestStatus


class IngestResult:
    """摄取结果。"""

    def __init__(
        self,
        source_id: str,
        status: IngestStatus,
        items_fetched: int = 0,
        items_new: int = 0,
        items_duplicate: int = 0,
        duration_ms: int = 0,
        error_message: str | None = None,
        new_item_ids: list[str] | None = None,
    ):
        self.source_id = source_id
        self.status = status
        self.items_fetched = items_fetched
        self.items_new = items_new
        self.items_duplicate = items_duplicate
        self.duration_ms = duration_ms
        self.error_message = error_message
        self.new_item_ids = new_item_ids or []

    @property
    def is_success(self) -> bool:
        return self.status in (IngestStatus.SUCCESS, IngestStatus.PARTIAL)


class IngestService:
    """信息摄取服务。

    职责：
    - 调用抓取器获取数据
    - URL 去重
    - 入库新条目
    - 更新源状态
    - 记录 ingest_log
    - 发布 ItemIngested 事件
    """

    def __init__(
        self,
        source_repository: SourceRepository,
        item_repository: ItemRepository,
        event_bus: EventBus,
    ):
        self.source_repository = source_repository
        self.item_repository = item_repository
        self.event_bus = event_bus

    async def ingest_source(self, source: Source) -> IngestResult:
        """执行单个源的抓取流程。

        Args:
            source: 要抓取的源

        Returns:
            IngestResult: 抓取结果
        """
        start_time = time.time()
        logger.info(f"Starting ingest for source: {source.name} ({source.id})")

        try:
            # 1. 创建抓取器并执行抓取
            fetcher = FetcherFactory.create(
                source_type=source.type,
                config=source.config,
                max_items=settings.ITEMS_PER_SOURCE_PER_FETCH,
            )

            fetch_result = await fetcher.fetch()

            # 2. 处理抓取结果
            if not fetch_result.is_success:
                # 抓取失败
                source.mark_fetch_error()
                await self.source_repository.update(source)

                # 发布失败事件
                await self.event_bus.publish(
                    SourceFetchErrorEvent(
                        source_id=source.id,
                        error=fetch_result.error_message or "Unknown error",
                        error_streak=source.error_streak,
                    )
                )

                duration_ms = int((time.time() - start_time) * 1000)
                return IngestResult(
                    source_id=source.id,
                    status=IngestStatus.FAILED,
                    duration_ms=duration_ms,
                    error_message=fetch_result.error_message,
                )

            # 3. 去重并入库
            new_items, duplicate_count = await self._dedupe_and_save(
                source=source,
                fetched_items=fetch_result.items,
            )

            # 4. 更新源状态
            source.mark_fetch_success(items_count=len(fetch_result.items))
            await self.source_repository.update(source)

            # 5. 发布成功事件
            await self.event_bus.publish(
                SourceFetchSuccessEvent(
                    source_id=source.id,
                    items_count=len(new_items),
                )
            )

            # 6. 为新条目发布 ItemIngested 事件（触发后续处理）
            for item in new_items:
                await self.event_bus.publish(
                    ItemIngestedEvent(
                        item_id=item.id,
                        source_id=item.source_id,
                        url=item.url,
                    )
                )

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"Ingest completed for {source.name}: "
                f"fetched={len(fetch_result.items)}, "
                f"new={len(new_items)}, "
                f"duplicate={duplicate_count}, "
                f"duration={duration_ms}ms"
            )

            return IngestResult(
                source_id=source.id,
                status=IngestStatus.SUCCESS,
                items_fetched=len(fetch_result.items),
                items_new=len(new_items),
                items_duplicate=duplicate_count,
                duration_ms=duration_ms,
                new_item_ids=[item.id for item in new_items],
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"Ingest error for {source.name}: {e}")

            # 更新源错误状态
            try:
                source.mark_fetch_error()
                await self.source_repository.update(source)

                await self.event_bus.publish(
                    SourceFetchErrorEvent(
                        source_id=source.id,
                        error=str(e),
                        error_streak=source.error_streak,
                    )
                )
            except Exception as update_error:
                logger.error(f"Failed to update source error status: {update_error}")

            return IngestResult(
                source_id=source.id,
                status=IngestStatus.FAILED,
                duration_ms=duration_ms,
                error_message=str(e),
            )

    async def _dedupe_and_save(
        self,
        source: Source,
        fetched_items: list[FetchedItem],
    ) -> tuple[list[Item], int]:
        """去重并保存新条目。

        Args:
            source: 源实体
            fetched_items: 抓取到的条目列表

        Returns:
            (新保存的条目列表, 重复条目数)
        """
        new_items: list[Item] = []
        duplicate_count = 0

        for fetched in fetched_items:
            # 计算 URL hash
            url_hash = self._compute_url_hash(fetched.url)

            # 检查是否已存在
            exists = await self.item_repository.exists_by_url_hash(url_hash)
            if exists:
                duplicate_count += 1
                continue

            # 创建新 Item 实体
            item = Item(
                source_id=source.id,
                url=fetched.url,
                url_hash=url_hash,
                title=fetched.title,
                snippet=fetched.snippet,
                published_at=fetched.published_at,
                ingested_at=datetime.now(UTC),
                embedding_status=EmbeddingStatus.PENDING,
                raw_data=fetched.raw_data,
            )

            # 保存到数据库
            try:
                saved_item = await self.item_repository.create(item)
                new_items.append(saved_item)
            except Exception as e:
                # 可能是并发导致的唯一键冲突
                logger.warning(f"Failed to save item {fetched.url}: {e}")
                duplicate_count += 1

        return new_items, duplicate_count

    @staticmethod
    def _compute_url_hash(url: str) -> str:
        """计算 URL 的哈希值。

        使用 SHA-256 并取前 32 个字符作为 hash。
        """
        # 标准化 URL
        normalized = url.strip().lower()
        # 移除尾部斜杠
        normalized = normalized.rstrip("/")

        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]

    async def ingest_source_by_id(self, source_id: str) -> IngestResult:
        """根据源 ID 执行抓取。

        Args:
            source_id: 源 ID

        Returns:
            IngestResult: 抓取结果
        """
        source = await self.source_repository.get_by_id(source_id)
        if not source:
            return IngestResult(
                source_id=source_id,
                status=IngestStatus.FAILED,
                error_message=f"Source not found: {source_id}",
            )

        if not source.enabled:
            return IngestResult(
                source_id=source_id,
                status=IngestStatus.FAILED,
                error_message=f"Source is disabled: {source_id}",
            )

        return await self.ingest_source(source)
