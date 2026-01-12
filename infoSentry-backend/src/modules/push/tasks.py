"""Push Celery tasks.

Includes:
- check_and_coalesce_immediate: Check and flush immediate buffers
- send_immediate_email: Send immediate email for a goal
- send_batch_email: Send batch email for a goal
- send_digest_email: Send digest email for a goal
- add_to_immediate_buffer: Add a decision to immediate buffer

Note: Scheduling tasks (check_and_trigger_batch_windows, check_and_send_digest)
are in agent/tasks.py to keep agent orchestration logic together.
"""

import asyncio
from datetime import UTC, datetime

from celery import shared_task
from loguru import logger

from src.core.infrastructure.celery.queues import Queues


@shared_task(
    name="src.modules.push.tasks.check_and_coalesce_immediate",
    bind=True,
    max_retries=0,
    queue=Queues.EMAIL,
)
def check_and_coalesce_immediate(_self: object) -> None:
    """Check and flush immediate coalesce buffers.

    Called by Celery Beat every minute.
    Flushes buffers that:
    - Are older than 5 minutes
    - Have reached max items (3)
    """
    asyncio.run(_check_and_coalesce_immediate_async())


async def _check_and_coalesce_immediate_async():
    """Async implementation of immediate buffer check."""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.core.infrastructure.redis.client import RedisClient
    from src.modules.goals.infrastructure.mappers import GoalMapper
    from src.modules.goals.infrastructure.repositories import PostgreSQLGoalRepository
    from src.modules.items.infrastructure.mappers import ItemMapper
    from src.modules.items.infrastructure.repositories import PostgreSQLItemRepository
    from src.modules.push.application.push_service import PushService
    from src.modules.push.infrastructure.mappers import PushDecisionMapper
    from src.modules.push.infrastructure.repositories import (
        PostgreSQLPushDecisionRepository,
    )
    from src.modules.sources.infrastructure.mappers import SourceMapper
    from src.modules.sources.infrastructure.repositories import (
        PostgreSQLSourceRepository,
    )
    from src.modules.users.infrastructure.mappers import UserMapper
    from src.modules.users.infrastructure.repositories import PostgreSQLUserRepository

    async with get_async_session() as session:
        try:
            event_bus = SimpleEventBus()
            redis_client = RedisClient()

            # Create repositories
            decision_repo = PostgreSQLPushDecisionRepository(
                session, PushDecisionMapper(), event_bus
            )
            goal_repo = PostgreSQLGoalRepository(session, GoalMapper(), event_bus)
            item_repo = PostgreSQLItemRepository(session, ItemMapper(), event_bus)
            source_repo = PostgreSQLSourceRepository(session, SourceMapper(), event_bus)
            user_repo = PostgreSQLUserRepository(session, UserMapper(), event_bus)

            # Create push service
            push_service = PushService(
                decision_repository=decision_repo,
                goal_repository=goal_repo,
                item_repository=item_repo,
                source_repository=source_repo,
                user_repository=user_repo,
                redis_client=redis_client,
            )

            # Check and flush buffers
            flushed_goals = await push_service.check_and_flush_immediate_buffers()

            if flushed_goals:
                logger.info(f"Flushed immediate buffers for {len(flushed_goals)} goals")

            await session.commit()

        except Exception as e:
            logger.exception(f"Error in check_and_coalesce_immediate: {e}")
            await session.rollback()


@shared_task(
    name="src.modules.push.tasks.send_immediate_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    queue=Queues.EMAIL,
)
def send_immediate_email(_self: object, goal_id: str, decision_ids: list[str]) -> None:
    """Send immediate email for a goal.

    Args:
        goal_id: Goal ID
        decision_ids: List of decision IDs to include
    """
    asyncio.run(_send_immediate_email_async(goal_id, decision_ids))


async def _send_immediate_email_async(goal_id: str, decision_ids: list[str]):
    """Async implementation of immediate email sending."""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.core.infrastructure.redis.client import RedisClient
    from src.modules.goals.infrastructure.mappers import GoalMapper
    from src.modules.goals.infrastructure.repositories import PostgreSQLGoalRepository
    from src.modules.items.infrastructure.mappers import ItemMapper
    from src.modules.items.infrastructure.repositories import PostgreSQLItemRepository
    from src.modules.push.application.push_service import PushService
    from src.modules.push.infrastructure.mappers import PushDecisionMapper
    from src.modules.push.infrastructure.repositories import (
        PostgreSQLPushDecisionRepository,
    )
    from src.modules.sources.infrastructure.mappers import SourceMapper
    from src.modules.sources.infrastructure.repositories import (
        PostgreSQLSourceRepository,
    )
    from src.modules.users.infrastructure.mappers import UserMapper
    from src.modules.users.infrastructure.repositories import PostgreSQLUserRepository

    async with get_async_session() as session:
        try:
            event_bus = SimpleEventBus()
            redis_client = RedisClient()

            # Create repositories
            decision_repo = PostgreSQLPushDecisionRepository(
                session, PushDecisionMapper(), event_bus
            )
            goal_repo = PostgreSQLGoalRepository(session, GoalMapper(), event_bus)
            item_repo = PostgreSQLItemRepository(session, ItemMapper(), event_bus)
            source_repo = PostgreSQLSourceRepository(session, SourceMapper(), event_bus)
            user_repo = PostgreSQLUserRepository(session, UserMapper(), event_bus)

            # Create push service
            push_service = PushService(
                decision_repository=decision_repo,
                goal_repository=goal_repo,
                item_repository=item_repo,
                source_repository=source_repo,
                user_repository=user_repo,
                redis_client=redis_client,
            )

            # Send email
            success = await push_service._send_immediate_email(goal_id, decision_ids)

            await session.commit()

            if success:
                logger.info(f"Immediate email sent for goal {goal_id}")
            else:
                logger.error(f"Failed to send immediate email for goal {goal_id}")
                raise Exception(f"Failed to send immediate email for goal {goal_id}")

        except Exception as e:
            logger.exception(f"Error in send_immediate_email: {e}")
            await session.rollback()
            raise


@shared_task(
    name="src.modules.push.tasks.send_batch_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    queue=Queues.EMAIL,
)
def send_batch_email(_self: object, goal_id: str, window_time: str) -> None:
    """Send batch email for a goal.

    Args:
        goal_id: Goal ID
        window_time: Batch window time (HH:MM)
    """
    asyncio.run(_send_batch_email_async(goal_id, window_time))


async def _send_batch_email_async(goal_id: str, window_time: str):
    """Async implementation of batch email sending."""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.core.infrastructure.redis.client import RedisClient
    from src.modules.goals.infrastructure.mappers import GoalMapper
    from src.modules.goals.infrastructure.repositories import PostgreSQLGoalRepository
    from src.modules.items.infrastructure.mappers import ItemMapper
    from src.modules.items.infrastructure.repositories import PostgreSQLItemRepository
    from src.modules.push.application.push_service import PushService
    from src.modules.push.infrastructure.mappers import PushDecisionMapper
    from src.modules.push.infrastructure.repositories import (
        PostgreSQLPushDecisionRepository,
    )
    from src.modules.sources.infrastructure.mappers import SourceMapper
    from src.modules.sources.infrastructure.repositories import (
        PostgreSQLSourceRepository,
    )
    from src.modules.users.infrastructure.mappers import UserMapper
    from src.modules.users.infrastructure.repositories import PostgreSQLUserRepository

    async with get_async_session() as session:
        try:
            event_bus = SimpleEventBus()
            redis_client = RedisClient()

            # Create repositories
            decision_repo = PostgreSQLPushDecisionRepository(
                session, PushDecisionMapper(), event_bus
            )
            goal_repo = PostgreSQLGoalRepository(session, GoalMapper(), event_bus)
            item_repo = PostgreSQLItemRepository(session, ItemMapper(), event_bus)
            source_repo = PostgreSQLSourceRepository(session, SourceMapper(), event_bus)
            user_repo = PostgreSQLUserRepository(session, UserMapper(), event_bus)

            # Create push service
            push_service = PushService(
                decision_repository=decision_repo,
                goal_repository=goal_repo,
                item_repository=item_repo,
                source_repository=source_repo,
                user_repository=user_repo,
                redis_client=redis_client,
            )

            # Send batch email
            success = await push_service.process_batch_window(goal_id, window_time)

            await session.commit()

            if success:
                logger.info(f"Batch email sent for goal {goal_id}")
            else:
                logger.error(f"Failed to send batch email for goal {goal_id}")
                raise Exception(f"Failed to send batch email for goal {goal_id}")

        except Exception as e:
            logger.exception(f"Error in send_batch_email: {e}")
            await session.rollback()
            raise


@shared_task(
    name="src.modules.push.tasks.send_digest_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    queue=Queues.EMAIL,
)
def send_digest_email(_self: object, goal_id: str) -> None:
    """Send digest email for a goal.

    Args:
        goal_id: Goal ID
    """
    asyncio.run(_send_digest_email_async(goal_id))


async def _send_digest_email_async(goal_id: str):
    """Async implementation of digest email sending."""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.core.infrastructure.redis.client import RedisClient
    from src.modules.goals.infrastructure.mappers import GoalMapper
    from src.modules.goals.infrastructure.repositories import PostgreSQLGoalRepository
    from src.modules.items.infrastructure.mappers import ItemMapper
    from src.modules.items.infrastructure.repositories import PostgreSQLItemRepository
    from src.modules.push.application.push_service import PushService
    from src.modules.push.infrastructure.mappers import PushDecisionMapper
    from src.modules.push.infrastructure.repositories import (
        PostgreSQLPushDecisionRepository,
    )
    from src.modules.sources.infrastructure.mappers import SourceMapper
    from src.modules.sources.infrastructure.repositories import (
        PostgreSQLSourceRepository,
    )
    from src.modules.users.infrastructure.mappers import UserMapper
    from src.modules.users.infrastructure.repositories import PostgreSQLUserRepository

    async with get_async_session() as session:
        try:
            event_bus = SimpleEventBus()
            redis_client = RedisClient()

            # Create repositories
            decision_repo = PostgreSQLPushDecisionRepository(
                session, PushDecisionMapper(), event_bus
            )
            goal_repo = PostgreSQLGoalRepository(session, GoalMapper(), event_bus)
            item_repo = PostgreSQLItemRepository(session, ItemMapper(), event_bus)
            source_repo = PostgreSQLSourceRepository(session, SourceMapper(), event_bus)
            user_repo = PostgreSQLUserRepository(session, UserMapper(), event_bus)

            # Create push service
            push_service = PushService(
                decision_repository=decision_repo,
                goal_repository=goal_repo,
                item_repository=item_repo,
                source_repository=source_repo,
                user_repository=user_repo,
                redis_client=redis_client,
            )

            # Send digest email
            success = await push_service.process_digest(goal_id)

            await session.commit()

            if success:
                logger.info(f"Digest email sent for goal {goal_id}")
            else:
                logger.error(f"Failed to send digest email for goal {goal_id}")
                raise Exception(f"Failed to send digest email for goal {goal_id}")

        except Exception as e:
            logger.exception(f"Error in send_digest_email: {e}")
            await session.rollback()
            raise


@shared_task(
    name="src.modules.push.tasks.add_to_immediate_buffer",
    bind=True,
    max_retries=2,
    queue=Queues.EMAIL,
)
def add_to_immediate_buffer(_self: object, goal_id: str, decision_id: str) -> None:
    """Add a decision to the immediate buffer.

    Called after a decision is made.
    The buffer will be flushed by check_and_coalesce_immediate.

    Args:
        goal_id: Goal ID
        decision_id: Decision ID
    """
    asyncio.run(_add_to_immediate_buffer_async(goal_id, decision_id))


async def _add_to_immediate_buffer_async(goal_id: str, decision_id: str):
    """Async implementation of adding to immediate buffer."""
    from src.core.config import settings
    from src.core.infrastructure.redis.client import RedisClient
    from src.core.infrastructure.redis.keys import RedisKeys

    redis_client = RedisClient()

    now = datetime.now(UTC)
    time_bucket = now.strftime("%Y%m%d%H") + str(now.minute // 5)
    buffer_key = RedisKeys.immediate_buffer(goal_id, time_bucket)

    current_size = await redis_client.llen(buffer_key)
    if current_size >= settings.IMMEDIATE_MAX_ITEMS:
        logger.info(f"Immediate buffer full for goal {goal_id}")
        return False

    await redis_client.rpush(buffer_key, decision_id)
    await redis_client.expire(buffer_key, 600)
    logger.debug(f"Added decision {decision_id} to immediate buffer for goal {goal_id}")
    return True
