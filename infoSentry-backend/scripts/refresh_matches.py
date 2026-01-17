#!/usr/bin/env python
"""刷新所有 Goal 的匹配记录。

使用新的余弦相似度计算逻辑重新计算匹配分数。

用法:
    uv run python scripts/refresh_matches.py [--hours 168] [--goal-id <goal_id>]
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _ensure_project_root_on_path() -> None:
    """确保项目根目录在 Python 路径中，便于直接运行脚本。"""
    project_root = Path(__file__).parent.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


_ensure_project_root_on_path()


async def refresh_matches_for_goal(
    goal_id: str,
    hours_back: int = 168,
) -> int:
    """刷新单个 Goal 的匹配记录。

    Args:
        goal_id: Goal ID
        hours_back: 向前查找的小时数

    Returns:
        创建的匹配数
    """
    from loguru import logger

    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.core.infrastructure.redis.client import RedisClient
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
        event_bus = SimpleEventBus()
        redis_client = RedisClient()

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
            return 0

        logger.info(f"Refreshing matches for goal: {goal.name} ({goal_id})")

        match_service = MatchService(
            goal_repository=goal_repo,
            term_repository=term_repo,
            item_repository=item_repo,
            match_repository=match_repo,
            event_bus=event_bus,
            redis_client=redis_client,
        )

        # 获取最近的 Items
        since = datetime.now(UTC) - timedelta(hours=hours_back)
        items, total = await item_repo.list_recent(since=since, page_size=1000)

        logger.info(f"Found {len(items)} items in the last {hours_back} hours")

        # 逐个匹配
        match_count = 0
        for i, item in enumerate(items):
            result = await match_service.match_item_to_goal(item, goal)
            if result.is_valid and result.score > 0:
                await match_service._save_match(result)
                match_count += 1

            # 进度日志
            if (i + 1) % 50 == 0:
                logger.info(f"  Progress: {i + 1}/{len(items)}, matches: {match_count}")

        await session.commit()
        logger.info(f"Created/updated {match_count} matches for goal {goal_id}")

        return match_count


async def refresh_all_goals(hours_back: int = 168) -> None:
    """刷新所有活跃 Goal 的匹配记录。"""
    from loguru import logger

    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.modules.goals.infrastructure.mappers import GoalMapper
    from src.modules.goals.infrastructure.repositories import PostgreSQLGoalRepository

    async with get_async_session() as session:
        event_bus = SimpleEventBus()
        goal_repo = PostgreSQLGoalRepository(session, GoalMapper(), event_bus)

        goals = await goal_repo.get_active_goals()
        logger.info(f"Found {len(goals)} active goals")

        total_matches = 0
        for goal in goals:
            count = await refresh_matches_for_goal(goal.id, hours_back)
            total_matches += count

        logger.info(f"Total matches created/updated: {total_matches}")


def main():
    parser = argparse.ArgumentParser(description="刷新 Goal 匹配记录")
    parser.add_argument(
        "--hours",
        type=int,
        default=168,
        help="向前查找的小时数（默认 168 = 7天）",
    )
    parser.add_argument(
        "--goal-id",
        type=str,
        default=None,
        help="指定 Goal ID（不指定则刷新所有活跃 Goal）",
    )

    args = parser.parse_args()

    if args.goal_id:
        asyncio.run(refresh_matches_for_goal(args.goal_id, args.hours))
    else:
        asyncio.run(refresh_all_goals(args.hours))


if __name__ == "__main__":
    main()
