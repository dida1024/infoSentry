"""信息源 Celery 任务。

包含：
- 检查并调度抓取任务
- 单个源的抓取任务
"""

from datetime import UTC, datetime

from celery import shared_task
from loguru import logger

from src.core.config import settings
from src.core.infrastructure.celery.queues import Queues


@shared_task(
    name="src.modules.sources.tasks.check_and_dispatch_fetches",
    bind=True,
    max_retries=0,  # 调度任务不重试
    queue=Queues.INGEST,
)
def check_and_dispatch_fetches(_self: object) -> None:
    """检查并调度需要抓取的源。

    由 Celery Beat 每分钟调用一次。
    查找 next_fetch_at <= now 的源，为每个源创建抓取任务。
    """
    import asyncio

    asyncio.run(_check_and_dispatch_fetches_async())


async def _check_and_dispatch_fetches_async() -> None:
    """异步版本的检查调度逻辑。"""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.modules.sources.infrastructure.mappers import SourceMapper
    from src.modules.sources.infrastructure.repositories import (
        PostgreSQLSourceRepository,
    )

    async with get_async_session() as session:
        try:
            # 获取到期需要抓取的源
            event_bus = SimpleEventBus()
            mapper = SourceMapper()
            source_repo = PostgreSQLSourceRepository(session, mapper, event_bus)

            sources = await source_repo.get_sources_due_for_fetch(
                before_time=datetime.now(UTC),
                limit=settings.INGEST_SOURCES_PER_MIN,
            )

            if not sources:
                logger.debug("No sources due for fetch")
                return

            logger.info(f"Dispatching fetch for {len(sources)} sources")

            # 为每个源创建抓取任务
            for source in sources:
                ingest_source.delay(source_id=source.id)

            await session.commit()

        except Exception as e:
            logger.exception(f"Error in check_and_dispatch_fetches: {e}")
            await session.rollback()
            raise


@shared_task(
    name="src.modules.sources.tasks.ingest_source",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    queue=Queues.INGEST,
)
def ingest_source(_self: object, source_id: str) -> None:
    """执行单个源的抓取任务。

    Args:
        source_id: 要抓取的源 ID
    """
    import asyncio

    asyncio.run(_ingest_source_async(source_id))


async def _ingest_source_async(source_id: str) -> None:
    """异步版本的抓取逻辑。"""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.modules.items.infrastructure.mappers import ItemMapper
    from src.modules.items.infrastructure.repositories import PostgreSQLItemRepository
    from src.modules.sources.application.ingest_service import IngestService
    from src.modules.sources.infrastructure.fetchers.factory import (
        InfrastructureFetcherFactory,
    )
    from src.modules.sources.infrastructure.ingest_log_repository import (
        IngestLogRepository,
    )
    from src.modules.sources.infrastructure.mappers import SourceMapper
    from src.modules.sources.infrastructure.repositories import (
        PostgreSQLSourceRepository,
    )

    started_at = datetime.now(UTC)

    async with get_async_session() as session:
        try:
            # 创建依赖
            event_bus = SimpleEventBus()
            source_mapper = SourceMapper()
            item_mapper = ItemMapper()

            source_repo = PostgreSQLSourceRepository(session, source_mapper, event_bus)
            item_repo = PostgreSQLItemRepository(session, item_mapper, event_bus)
            ingest_log_repo = IngestLogRepository(session)

            # 创建服务
            ingest_service = IngestService(
                source_repository=source_repo,
                item_repository=item_repo,
                event_bus=event_bus,
                fetcher_factory=InfrastructureFetcherFactory(),
            )

            # 执行抓取
            result = await ingest_service.ingest_source_by_id(source_id)

            # 记录日志
            await ingest_log_repo.create_from_result(result, started_at)

            # 如果有新条目，触发后续处理（投递到 embed 队列）
            if result.new_item_ids:
                for item_id in result.new_item_ids:
                    enqueue_embed_task.delay(item_id=item_id)

            await session.commit()

            if not result.is_success:
                logger.warning(
                    f"Ingest failed for source {source_id}: {result.error_message}"
                )
            else:
                logger.info(
                    f"Ingest completed for source {source_id}: "
                    f"new={result.items_new}, duplicate={result.items_duplicate}"
                )

        except Exception as e:
            logger.exception(f"Error in ingest_source task for {source_id}: {e}")
            await session.rollback()
            raise


@shared_task(
    name="src.modules.sources.tasks.enqueue_embed_task",
    bind=True,
    queue=Queues.EMBED,
)
def enqueue_embed_task(_self: object, item_id: str) -> None:
    """将条目投递到 embed 队列。

    调用 items 模块的 embed_item 任务进行实际的 embedding。
    """
    logger.info(f"Item {item_id} enqueued for embedding")
    from src.modules.items.tasks import embed_item

    embed_item.delay(item_id=item_id)


# ============================================
# 手动触发任务（用于调试/管理）
# ============================================


@shared_task(
    name="src.modules.sources.tasks.force_ingest_all",
    bind=True,
    queue=Queues.INGEST,
)
def force_ingest_all(_self: object, source_type: str | None = None) -> None:
    """强制抓取所有启用的源（忽略调度时间）。

    Args:
        source_type: 可选，只抓取特定类型的源（NEWSNOW/RSS/SITE）
    """
    import asyncio

    asyncio.run(_force_ingest_all_async(source_type))


async def _force_ingest_all_async(source_type: str | None) -> None:
    """异步版本的强制抓取。"""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.modules.sources.domain.entities import SourceType
    from src.modules.sources.infrastructure.mappers import SourceMapper
    from src.modules.sources.infrastructure.repositories import (
        PostgreSQLSourceRepository,
    )

    async with get_async_session() as session:
        try:
            event_bus = SimpleEventBus()
            mapper = SourceMapper()
            source_repo = PostgreSQLSourceRepository(session, mapper, event_bus)

            # 获取启用的源
            source_type_filter = None
            if source_type:
                source_type_filter = SourceType(source_type)

            sources, _ = await source_repo.list_by_type(
                source_type=source_type_filter,
                enabled_only=True,
                page=1,
                page_size=settings.FORCE_INGEST_PAGE_SIZE,
            )

            logger.info(f"Force ingesting {len(sources)} sources")

            for source in sources:
                ingest_source.delay(source_id=source.id)

            await session.commit()

        except Exception as e:
            logger.exception(f"Error in force_ingest_all: {e}")
            await session.rollback()
            raise
