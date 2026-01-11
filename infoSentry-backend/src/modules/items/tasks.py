"""Items Celery 任务。

包含：
- embed_item: 单个 Item 嵌入任务
- embed_pending_items: 批量嵌入待处理 Items
- match_item: 单个 Item 匹配任务
- match_items_batch: 批量匹配任务
"""

from datetime import UTC, datetime, timedelta

from celery import shared_task
from loguru import logger

from src.core.config import settings
from src.core.infrastructure.celery.queues import Queues


@shared_task(
    name="src.modules.items.tasks.embed_item",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    queue=Queues.EMBED,
)
def embed_item(self, item_id: str):
    """为单个 Item 生成嵌入向量。

    Args:
        item_id: Item ID
    """
    import asyncio

    asyncio.run(_embed_item_async(item_id))


async def _embed_item_async(item_id: str):
    """异步版本的嵌入任务。"""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.core.infrastructure.redis.client import RedisClient
    from src.modules.items.application.budget_service import BudgetService
    from src.modules.items.application.embedding_service import EmbeddingService
    from src.modules.items.infrastructure.mappers import ItemMapper
    from src.modules.items.infrastructure.repositories import PostgreSQLItemRepository

    async with get_async_session() as session:
        try:
            # 创建依赖
            event_bus = SimpleEventBus()
            item_mapper = ItemMapper()
            redis_client = RedisClient()

            item_repo = PostgreSQLItemRepository(session, item_mapper, event_bus)
            budget_service = BudgetService(redis_client)
            embedding_service = EmbeddingService(
                item_repository=item_repo,
                budget_service=budget_service,
            )

            # 获取 Item
            item = await item_repo.get_by_id(item_id)
            if not item:
                logger.warning(f"Item not found: {item_id}")
                return

            # 执行嵌入
            result = await embedding_service.embed_item(item)

            await session.commit()

            if result.success:
                logger.info(f"Embedded item {item_id}, tokens: {result.tokens_used}")
                # 触发匹配任务
                match_item.delay(item_id=item_id)
            else:
                logger.warning(f"Embed failed for {item_id}: {result.error}")

        except Exception as e:
            logger.exception(f"Error in embed_item task for {item_id}: {e}")
            await session.rollback()
            raise


@shared_task(
    name="src.modules.items.tasks.embed_pending_items",
    bind=True,
    max_retries=0,
    queue=Queues.EMBED,
)
def embed_pending_items(self, limit: int = 100):
    """批量处理待嵌入的 Items。

    由 Celery Beat 定期调用或手动触发。

    Args:
        limit: 每次处理的最大数量
    """
    import asyncio

    asyncio.run(_embed_pending_items_async(limit))


async def _embed_pending_items_async(limit: int):
    """异步版本的批量嵌入任务。"""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.core.infrastructure.redis.client import RedisClient
    from src.modules.items.application.budget_service import BudgetService
    from src.modules.items.application.embedding_service import EmbeddingService
    from src.modules.items.infrastructure.mappers import ItemMapper
    from src.modules.items.infrastructure.repositories import PostgreSQLItemRepository

    async with get_async_session() as session:
        try:
            # 创建依赖
            event_bus = SimpleEventBus()
            item_mapper = ItemMapper()
            redis_client = RedisClient()

            item_repo = PostgreSQLItemRepository(session, item_mapper, event_bus)
            budget_service = BudgetService(redis_client)
            embedding_service = EmbeddingService(
                item_repository=item_repo,
                budget_service=budget_service,
            )

            # 获取待处理 Items
            items = await item_repo.list_pending_embedding(limit=limit)

            if not items:
                logger.debug("No pending items to embed")
                return

            logger.info(f"Embedding {len(items)} pending items")

            # 批量嵌入
            results = await embedding_service.embed_items_batch(items)

            await session.commit()

            # 统计结果
            success_count = sum(1 for r in results if r.success)
            logger.info(f"Embedded {success_count}/{len(results)} items")

            # 为成功的 Items 触发匹配任务
            for result in results:
                if result.success:
                    match_item.delay(item_id=result.item_id)

        except Exception as e:
            logger.exception(f"Error in embed_pending_items: {e}")
            await session.rollback()
            raise


@shared_task(
    name="src.modules.items.tasks.match_item",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    queue=Queues.MATCH,
)
def match_item(self, item_id: str):
    """计算单个 Item 与所有活跃 Goals 的匹配。

    Args:
        item_id: Item ID
    """
    import asyncio

    asyncio.run(_match_item_async(item_id))


async def _match_item_async(item_id: str):
    """异步版本的匹配任务。"""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.modules.goals.infrastructure.mappers import (
        GoalMapper,
        GoalPriorityTermMapper,
    )
    from src.modules.goals.infrastructure.repositories import (
        PostgreSQLGoalPriorityTermRepository,
        PostgreSQLGoalRepository,
    )
    from src.modules.items.application.match_service import MatchService
    from src.modules.items.infrastructure.mappers import GoalItemMatchMapper, ItemMapper
    from src.modules.items.infrastructure.repositories import (
        PostgreSQLGoalItemMatchRepository,
        PostgreSQLItemRepository,
    )

    async with get_async_session() as session:
        try:
            # 创建依赖
            event_bus = SimpleEventBus()

            goal_repo = PostgreSQLGoalRepository(session, GoalMapper(), event_bus)
            term_repo = PostgreSQLGoalPriorityTermRepository(
                session, GoalPriorityTermMapper(), event_bus
            )
            item_repo = PostgreSQLItemRepository(session, ItemMapper(), event_bus)
            match_repo = PostgreSQLGoalItemMatchRepository(
                session, GoalItemMatchMapper(), event_bus
            )

            match_service = MatchService(
                goal_repository=goal_repo,
                term_repository=term_repo,
                item_repository=item_repo,
                match_repository=match_repo,
                event_bus=event_bus,
            )

            # 执行匹配
            results = await match_service.match_item_by_id(item_id)

            await session.commit()

            # 统计结果
            valid_matches = [r for r in results if r.is_valid and r.score > 0]
            logger.info(
                f"Matched item {item_id} to {len(valid_matches)} goals "
                f"(total: {len(results)})"
            )

            # 高分匹配记录日志
            for r in valid_matches:
                if r.score >= settings.BATCH_THRESHOLD:
                    logger.info(
                        f"  -> goal={r.goal_id}, score={r.score:.4f}, "
                        f"reason={r.reasons.summary}"
                    )

        except Exception as e:
            logger.exception(f"Error in match_item task for {item_id}: {e}")
            await session.rollback()
            raise


@shared_task(
    name="src.modules.items.tasks.match_items_for_goal",
    bind=True,
    max_retries=0,
    queue=Queues.MATCH,
)
def match_items_for_goal(self, goal_id: str, hours_back: int = 24):
    """为特定 Goal 重新计算最近 Items 的匹配。

    用于 Goal 创建或更新后的重新匹配。

    Args:
        goal_id: Goal ID
        hours_back: 向前查找的小时数
    """
    import asyncio

    asyncio.run(_match_items_for_goal_async(goal_id, hours_back))


async def _match_items_for_goal_async(goal_id: str, hours_back: int):
    """异步版本的 Goal 匹配任务。"""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.modules.goals.infrastructure.mappers import (
        GoalMapper,
        GoalPriorityTermMapper,
    )
    from src.modules.goals.infrastructure.repositories import (
        PostgreSQLGoalPriorityTermRepository,
        PostgreSQLGoalRepository,
    )
    from src.modules.items.application.match_service import MatchService
    from src.modules.items.infrastructure.mappers import GoalItemMatchMapper, ItemMapper
    from src.modules.items.infrastructure.repositories import (
        PostgreSQLGoalItemMatchRepository,
        PostgreSQLItemRepository,
    )

    async with get_async_session() as session:
        try:
            # 创建依赖
            event_bus = SimpleEventBus()

            goal_repo = PostgreSQLGoalRepository(session, GoalMapper(), event_bus)
            term_repo = PostgreSQLGoalPriorityTermRepository(
                session, GoalPriorityTermMapper(), event_bus
            )
            item_repo = PostgreSQLItemRepository(session, ItemMapper(), event_bus)
            match_repo = PostgreSQLGoalItemMatchRepository(
                session, GoalItemMatchMapper(), event_bus
            )

            # 获取 Goal
            goal = await goal_repo.get_by_id(goal_id)
            if not goal:
                logger.warning(f"Goal not found: {goal_id}")
                return

            if not goal.is_active():
                logger.info(f"Goal {goal_id} is not active, skipping")
                return

            match_service = MatchService(
                goal_repository=goal_repo,
                term_repository=term_repo,
                item_repository=item_repo,
                match_repository=match_repo,
                event_bus=event_bus,
            )

            # 获取最近的 Items
            since = datetime.now(UTC) - timedelta(hours=hours_back)
            items, _ = await item_repo.list_recent(since=since, page_size=500)

            logger.info(f"Matching {len(items)} items to goal {goal_id}")

            # 逐个匹配
            match_count = 0
            for item in items:
                result = await match_service.match_item_to_goal(item, goal)
                if result.is_valid and result.score > 0:
                    await match_service._save_match(result)
                    match_count += 1

            await session.commit()
            logger.info(f"Created {match_count} matches for goal {goal_id}")

        except Exception as e:
            logger.exception(f"Error in match_items_for_goal: {e}")
            await session.rollback()
            raise
