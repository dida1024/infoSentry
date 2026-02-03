"""Agent Celery 任务。

包含：
- handle_match_computed: 处理 MatchComputed 事件
- check_and_trigger_batch_windows: 检查并触发 Batch 窗口
- check_and_send_digest: 检查并发送 Digest
- check_and_update_budget: 检查并更新预算状态
"""

from datetime import UTC, datetime

from celery import shared_task
from loguru import logger

from src.core.config import settings
from src.core.infrastructure.celery.queues import Queues
from src.core.infrastructure.celery.retry import DEFAULT_RETRYABLE_EXCEPTIONS


@shared_task(
    name="src.modules.agent.tasks.handle_match_computed",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=DEFAULT_RETRYABLE_EXCEPTIONS,
    retry_backoff=True,
    queue=Queues.AGENT,
)
def handle_match_computed(
    _self: object,
    goal_id: str,
    item_id: str,
    match_score: float,
    match_features: dict,
):
    """处理 MatchComputed 事件，执行 Agent 决策。

    Args:
        goal_id: Goal ID
        item_id: Item ID
        match_score: 匹配分数
        match_features: 匹配特征
    """
    import asyncio

    asyncio.run(
        _handle_match_computed_async(goal_id, item_id, match_score, match_features)
    )


async def _handle_match_computed_async(
    goal_id: str,
    item_id: str,
    match_score: float,
    match_features: dict,
):
    """异步版本的 MatchComputed 处理。"""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.ai.prompting.dependencies import (
        get_prompt_store as get_prompt_store_infra,
    )
    from src.core.infrastructure.database.session import get_async_session
    from src.core.infrastructure.redis.client import get_async_redis_client
    from src.modules.agent.application.llm_service import LLMJudgeService
    from src.modules.agent.application.nodes import create_immediate_pipeline
    from src.modules.agent.application.orchestrator import AgentOrchestrator
    from src.modules.agent.application.tools import create_default_registry
    from src.modules.agent.infrastructure.mappers import (
        AgentActionLedgerMapper,
        AgentRunMapper,
        AgentToolCallMapper,
    )
    from src.modules.agent.infrastructure.repositories import (
        PostgreSQLAgentActionLedgerRepository,
        PostgreSQLAgentRunRepository,
        PostgreSQLAgentToolCallRepository,
    )
    from src.modules.goals.infrastructure.mappers import (
        GoalMapper,
        GoalPriorityTermMapper,
    )
    from src.modules.goals.infrastructure.repositories import (
        PostgreSQLGoalPriorityTermRepository,
        PostgreSQLGoalRepository,
    )
    from src.modules.items.application.budget_service import BudgetService
    from src.modules.items.infrastructure.mappers import ItemMapper
    from src.modules.items.infrastructure.repositories import PostgreSQLItemRepository
    from src.modules.push.infrastructure.mappers import PushDecisionMapper
    from src.modules.push.infrastructure.repositories import (
        PostgreSQLPushDecisionRepository,
    )
    from src.modules.users.application.budget_service import UserBudgetUsageService
    from src.modules.users.infrastructure.mappers import UserBudgetDailyMapper
    from src.modules.users.infrastructure.repositories import (
        PostgreSQLUserBudgetDailyRepository,
    )

    async with (
        get_async_redis_client(
            timeout=settings.REDIS_CLIENT_TIMEOUT_SEC
        ) as redis_client,
        get_async_session() as session,
    ):
        try:
            event_bus = SimpleEventBus()

            # 创建 repositories
            run_repo = PostgreSQLAgentRunRepository(
                session, AgentRunMapper(), event_bus
            )
            tool_call_repo = PostgreSQLAgentToolCallRepository(
                session, AgentToolCallMapper(), event_bus
            )
            ledger_repo = PostgreSQLAgentActionLedgerRepository(
                session, AgentActionLedgerMapper(), event_bus
            )
            goal_repo = PostgreSQLGoalRepository(session, GoalMapper(), event_bus)
            term_repo = PostgreSQLGoalPriorityTermRepository(
                session, GoalPriorityTermMapper(), event_bus
            )
            item_repo = PostgreSQLItemRepository(session, ItemMapper(), event_bus)
            decision_repo = PostgreSQLPushDecisionRepository(
                session, PushDecisionMapper(), event_bus
            )
            user_budget_repo = PostgreSQLUserBudgetDailyRepository(
                session, UserBudgetDailyMapper(), event_bus
            )

            # 创建服务
            budget_service = BudgetService(redis_client)
            user_budget_service = UserBudgetUsageService(user_budget_repo)
            prompt_store = get_prompt_store_infra()
            llm_service = LLMJudgeService(
                budget_service=budget_service,
                user_budget_service=user_budget_service,
                prompt_store=prompt_store,
            )

            # 创建工具注册表
            tools = create_default_registry(
                goal_repository=goal_repo,
                term_repository=term_repo,
                item_repository=item_repo,
                decision_repository=decision_repo,
                budget_service=budget_service,
                redis_client=redis_client,
                ledger_repo=ledger_repo,
            )

            # 创建 Pipeline
            pipeline = create_immediate_pipeline(
                tools=tools,
                llm_service=llm_service,
                redis_client=redis_client,
            )

            # 创建编排器
            orchestrator = AgentOrchestrator(
                run_repository=run_repo,
                tool_call_repository=tool_call_repo,
                ledger_repository=ledger_repo,
                tools=tools,
                pipeline=pipeline,
                event_bus=event_bus,
                llm_service=llm_service,
            )

            # 获取匹配原因（从 goal_item_matches 表）
            from src.modules.items.infrastructure.mappers import GoalItemMatchMapper
            from src.modules.items.infrastructure.repositories import (
                PostgreSQLGoalItemMatchRepository,
            )

            match_repo = PostgreSQLGoalItemMatchRepository(
                session, GoalItemMatchMapper(), event_bus
            )
            match_record = await match_repo.get_by_goal_and_item(goal_id, item_id)
            match_reasons = match_record.reasons_json if match_record else {}

            # 执行 Agent
            run = await orchestrator.run_immediate(
                goal_id=goal_id,
                item_id=item_id,
                match_score=match_score,
                match_features=match_features,
                match_reasons=match_reasons,
                match_repository=match_repo,
            )

            await session.commit()

            logger.info(
                f"Agent run completed: {run.id}, "
                f"status={run.status.value}, "
                f"actions={len(run.final_actions_json)}"
            )

        except Exception as e:
            logger.exception(f"Error in handle_match_computed: {e}")
            await session.rollback()
            raise


@shared_task(
    name="src.modules.agent.tasks.check_and_trigger_batch_windows",
    bind=True,
    max_retries=0,
    queue=Queues.AGENT,
)
def check_and_trigger_batch_windows(_self: object) -> None:
    """检查并触发 Batch 窗口。

    由 Celery Beat 每分钟调用。
    """
    import asyncio

    asyncio.run(_check_and_trigger_batch_windows_async())


async def _check_and_trigger_batch_windows_async() -> None:
    """异步版本的 Batch 窗口检查。"""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.modules.goals.infrastructure.mappers import (
        GoalMapper,
        GoalPushConfigMapper,
    )
    from src.modules.goals.infrastructure.repositories import (
        PostgreSQLGoalPushConfigRepository,
        PostgreSQLGoalRepository,
    )

    async with get_async_session() as session:
        try:
            event_bus = SimpleEventBus()

            goal_repo = PostgreSQLGoalRepository(session, GoalMapper(), event_bus)
            config_repo = PostgreSQLGoalPushConfigRepository(
                session, GoalPushConfigMapper(), event_bus
            )

            # 获取当前时间（Asia/Shanghai）
            now = datetime.now(UTC)
            try:
                import pytz

                tz = pytz.timezone("Asia/Shanghai")
                now_local = now.astimezone(tz)
            except Exception as e:
                logger.warning(f"Failed to convert timezone, using UTC: {e}")
                now_local = now

            current_time = now_local.strftime("%H:%M")

            # 获取所有活跃 Goals
            active_goals = await goal_repo.get_active_goals()

            for goal in active_goals:
                # 获取 push config
                config = await config_repo.get_by_goal_id(goal.id)
                if not config or not config.batch_enabled:
                    continue

                # 检查是否在 batch_windows 中
                if current_time in config.batch_windows:
                    logger.info(
                        f"Triggering batch window for goal {goal.id} at {current_time}"
                    )
                    # 触发 Batch 任务
                    trigger_batch_for_goal.delay(
                        goal_id=goal.id, window_time=current_time
                    )

        except Exception as e:
            logger.exception(f"Error in check_and_trigger_batch_windows: {e}")


@shared_task(
    name="src.modules.agent.tasks.trigger_batch_for_goal",
    bind=True,
    max_retries=2,
    queue=Queues.AGENT,
)
def trigger_batch_for_goal(_self: object, goal_id: str, window_time: str) -> None:
    """为特定 Goal 触发 Batch 推送。

    Args:
        goal_id: Goal ID
        window_time: 窗口时间
    """
    import asyncio

    asyncio.run(_trigger_batch_for_goal_async(goal_id, window_time))


async def _trigger_batch_for_goal_async(goal_id: str, window_time: str) -> None:
    """异步版本的 Batch 触发。"""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.ai.prompting.dependencies import (
        get_prompt_store as get_prompt_store_infra,
    )
    from src.core.infrastructure.database.session import get_async_session
    from src.core.infrastructure.redis.client import get_async_redis_client
    from src.modules.agent.application.llm_service import LLMJudgeService
    from src.modules.agent.application.orchestrator import AgentOrchestrator
    from src.modules.agent.application.tools import ToolRegistry
    from src.modules.agent.infrastructure.mappers import (
        AgentActionLedgerMapper,
        AgentRunMapper,
        AgentToolCallMapper,
    )
    from src.modules.agent.infrastructure.repositories import (
        PostgreSQLAgentActionLedgerRepository,
        PostgreSQLAgentRunRepository,
        PostgreSQLAgentToolCallRepository,
    )
    from src.modules.goals.infrastructure.mappers import GoalMapper
    from src.modules.goals.infrastructure.repositories import PostgreSQLGoalRepository
    from src.modules.items.application.budget_service import BudgetService
    from src.modules.items.infrastructure.mappers import GoalItemMatchMapper, ItemMapper
    from src.modules.items.infrastructure.repositories import (
        PostgreSQLGoalItemMatchRepository,
        PostgreSQLItemRepository,
    )
    from src.modules.push.infrastructure.mappers import PushDecisionMapper
    from src.modules.push.infrastructure.repositories import (
        PostgreSQLPushDecisionRepository,
    )
    from src.modules.users.application.budget_service import UserBudgetUsageService
    from src.modules.users.infrastructure.mappers import UserBudgetDailyMapper
    from src.modules.users.infrastructure.repositories import (
        PostgreSQLUserBudgetDailyRepository,
    )

    async with (
        get_async_redis_client(
            timeout=settings.REDIS_CLIENT_TIMEOUT_SEC
        ) as redis_client,
        get_async_session() as session,
    ):
        try:
            event_bus = SimpleEventBus()

            run_repo = PostgreSQLAgentRunRepository(
                session, AgentRunMapper(), event_bus
            )
            tool_call_repo = PostgreSQLAgentToolCallRepository(
                session, AgentToolCallMapper(), event_bus
            )
            ledger_repo = PostgreSQLAgentActionLedgerRepository(
                session, AgentActionLedgerMapper(), event_bus
            )
            match_repo = PostgreSQLGoalItemMatchRepository(
                session, GoalItemMatchMapper(), event_bus
            )
            decision_repo = PostgreSQLPushDecisionRepository(
                session, PushDecisionMapper(), event_bus
            )
            goal_repo = PostgreSQLGoalRepository(session, GoalMapper(), event_bus)
            item_repo = PostgreSQLItemRepository(session, ItemMapper(), event_bus)
            user_budget_repo = PostgreSQLUserBudgetDailyRepository(
                session, UserBudgetDailyMapper(), event_bus
            )

            budget_service = BudgetService(redis_client)
            user_budget_service = UserBudgetUsageService(user_budget_repo)
            prompt_store = get_prompt_store_infra()
            llm_service = LLMJudgeService(
                budget_service=budget_service,
                user_budget_service=user_budget_service,
                prompt_store=prompt_store,
            )

            tools = ToolRegistry()
            orchestrator = AgentOrchestrator(
                run_repository=run_repo,
                tool_call_repository=tool_call_repo,
                ledger_repository=ledger_repo,
                tools=tools,
                llm_service=llm_service,
            )

            run = await orchestrator.run_batch_window(
                goal_id,
                window_time,
                match_repository=match_repo,
                decision_repository=decision_repo,
                goal_repository=goal_repo,
                item_repository=item_repo,
            )
            await session.commit()

            logger.info(f"Batch run completed: {run.id} for goal {goal_id}")

            # 触发发送批量邮件
            from src.modules.push.tasks import send_batch_email

            send_batch_email.delay(goal_id=goal_id, window_time=window_time)

        except Exception as e:
            logger.exception(f"Error in trigger_batch_for_goal: {e}")
            await session.rollback()
            raise


@shared_task(
    name="src.modules.agent.tasks.check_and_send_digest",
    bind=True,
    max_retries=0,
    queue=Queues.AGENT,
)
def check_and_send_digest(_self: object) -> None:
    """检查并发送 Digest。

    由 Celery Beat 每 5 分钟调用。
    """
    import asyncio

    asyncio.run(_check_and_send_digest_async())


async def _check_and_send_digest_async() -> None:
    """异步版本的 Digest 检查。"""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.modules.goals.infrastructure.mappers import (
        GoalMapper,
        GoalPushConfigMapper,
    )
    from src.modules.goals.infrastructure.repositories import (
        PostgreSQLGoalPushConfigRepository,
        PostgreSQLGoalRepository,
    )

    async with get_async_session() as session:
        try:
            event_bus = SimpleEventBus()

            goal_repo = PostgreSQLGoalRepository(session, GoalMapper(), event_bus)
            config_repo = PostgreSQLGoalPushConfigRepository(
                session, GoalPushConfigMapper(), event_bus
            )

            # 获取当前时间（Asia/Shanghai）
            now = datetime.now(UTC)
            try:
                import pytz

                tz = pytz.timezone("Asia/Shanghai")
                now_local = now.astimezone(tz)
            except Exception as e:
                logger.warning(f"Failed to convert timezone, using UTC: {e}")
                now_local = now

            current_time = now_local.strftime("%H:%M")

            # 获取所有活跃 Goals
            active_goals = await goal_repo.get_active_goals()

            for goal in active_goals:
                config = await config_repo.get_by_goal_id(goal.id)
                if not config or not config.digest_enabled:
                    continue

                # 检查是否是 digest 时间
                if current_time == config.digest_send_time:
                    logger.info(f"Triggering digest for goal {goal.id}")
                    trigger_digest_for_goal.delay(goal_id=goal.id)

        except Exception as e:
            logger.exception(f"Error in check_and_send_digest: {e}")


@shared_task(
    name="src.modules.agent.tasks.trigger_digest_for_goal",
    bind=True,
    max_retries=2,
    queue=Queues.AGENT,
)
def trigger_digest_for_goal(_self: object, goal_id: str) -> None:
    """为特定 Goal 触发 Digest 推送。

    Args:
        goal_id: Goal ID
    """
    import asyncio

    asyncio.run(_trigger_digest_for_goal_async(goal_id))


async def _trigger_digest_for_goal_async(goal_id: str) -> None:
    """异步版本的 Digest 触发。"""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.ai.prompting.dependencies import (
        get_prompt_store as get_prompt_store_infra,
    )
    from src.core.infrastructure.database.session import get_async_session
    from src.core.infrastructure.redis.client import get_async_redis_client
    from src.modules.agent.application.llm_service import LLMJudgeService
    from src.modules.agent.application.orchestrator import AgentOrchestrator
    from src.modules.agent.application.tools import ToolRegistry
    from src.modules.agent.infrastructure.mappers import (
        AgentActionLedgerMapper,
        AgentRunMapper,
        AgentToolCallMapper,
    )
    from src.modules.agent.infrastructure.repositories import (
        PostgreSQLAgentActionLedgerRepository,
        PostgreSQLAgentRunRepository,
        PostgreSQLAgentToolCallRepository,
    )
    from src.modules.goals.infrastructure.mappers import GoalMapper
    from src.modules.goals.infrastructure.repositories import PostgreSQLGoalRepository
    from src.modules.items.application.budget_service import BudgetService
    from src.modules.items.infrastructure.mappers import GoalItemMatchMapper, ItemMapper
    from src.modules.items.infrastructure.repositories import (
        PostgreSQLGoalItemMatchRepository,
        PostgreSQLItemRepository,
    )
    from src.modules.push.infrastructure.mappers import PushDecisionMapper
    from src.modules.push.infrastructure.repositories import (
        PostgreSQLPushDecisionRepository,
    )
    from src.modules.users.application.budget_service import UserBudgetUsageService
    from src.modules.users.infrastructure.mappers import UserBudgetDailyMapper
    from src.modules.users.infrastructure.repositories import (
        PostgreSQLUserBudgetDailyRepository,
    )

    async with (
        get_async_redis_client(
            timeout=settings.REDIS_CLIENT_TIMEOUT_SEC
        ) as redis_client,
        get_async_session() as session,
    ):
        try:
            event_bus = SimpleEventBus()

            run_repo = PostgreSQLAgentRunRepository(
                session, AgentRunMapper(), event_bus
            )
            tool_call_repo = PostgreSQLAgentToolCallRepository(
                session, AgentToolCallMapper(), event_bus
            )
            ledger_repo = PostgreSQLAgentActionLedgerRepository(
                session, AgentActionLedgerMapper(), event_bus
            )
            match_repo = PostgreSQLGoalItemMatchRepository(
                session, GoalItemMatchMapper(), event_bus
            )
            decision_repo = PostgreSQLPushDecisionRepository(
                session, PushDecisionMapper(), event_bus
            )
            goal_repo = PostgreSQLGoalRepository(session, GoalMapper(), event_bus)
            item_repo = PostgreSQLItemRepository(session, ItemMapper(), event_bus)
            user_budget_repo = PostgreSQLUserBudgetDailyRepository(
                session, UserBudgetDailyMapper(), event_bus
            )

            budget_service = BudgetService(redis_client)
            user_budget_service = UserBudgetUsageService(user_budget_repo)
            prompt_store = get_prompt_store_infra()
            llm_service = LLMJudgeService(
                budget_service=budget_service,
                user_budget_service=user_budget_service,
                prompt_store=prompt_store,
            )

            tools = ToolRegistry()
            orchestrator = AgentOrchestrator(
                run_repository=run_repo,
                tool_call_repository=tool_call_repo,
                ledger_repository=ledger_repo,
                tools=tools,
                llm_service=llm_service,
            )

            run = await orchestrator.run_digest(
                goal_id,
                match_repository=match_repo,
                decision_repository=decision_repo,
                goal_repository=goal_repo,
                item_repository=item_repo,
            )
            await session.commit()

            logger.info(f"Digest run completed: {run.id} for goal {goal_id}")

            # 触发发送摘要邮件
            from src.modules.push.tasks import send_digest_email

            send_digest_email.delay(goal_id=goal_id)

        except Exception as e:
            logger.exception(f"Error in trigger_digest_for_goal: {e}")
            await session.rollback()
            raise


@shared_task(
    name="src.modules.agent.tasks.check_and_update_budget",
    bind=True,
    max_retries=0,
    queue=Queues.AGENT,
)
def check_and_update_budget(_self: object) -> None:
    """检查并更新预算状态。

    由 Celery Beat 每小时调用。
    同步 Redis 中的预算状态到数据库。
    """
    import asyncio

    asyncio.run(_check_and_update_budget_async())


@shared_task(
    name="src.modules.agent.tasks.run_health_check",
    bind=True,
    max_retries=0,
    queue=Queues.AGENT,
)
def run_health_check(_self: object) -> None:
    """执行健康检查。

    由 Celery Beat 每 5 分钟调用。
    """
    import asyncio

    asyncio.run(_run_health_check_async())


async def _run_health_check_async() -> None:
    """异步版本的健康检查。"""
    from src.core.infrastructure.redis.client import get_async_redis_client
    from src.modules.agent.application.monitoring_service import MonitoringService

    try:
        async with get_async_redis_client(
            timeout=settings.REDIS_CLIENT_TIMEOUT_SEC
        ) as redis_client:
            monitoring = MonitoringService(redis_client)

            status = await monitoring.check_all()

            # 记录状态
            if status.healthy:
                logger.info(
                    f"Health check passed: {len(status.components)} components OK"
                )
            else:
                logger.warning(
                    f"Health check failed: status={status.status}, "
                    f"alerts={len(status.alerts)}"
                )
                for alert in status.alerts:
                    logger.warning(
                        f"  - [{alert.level.value}] {alert.source}: {alert.message}"
                    )

    except Exception as e:
        logger.exception(f"Error in health check: {e}")


@shared_task(
    name="src.modules.agent.tasks.record_worker_heartbeat",
    bind=True,
    max_retries=0,
)
def record_worker_heartbeat(_self: object, worker_type: str) -> None:
    """记录 Worker 心跳。

    Args:
        worker_type: Worker 类型
    """
    import asyncio

    asyncio.run(_record_worker_heartbeat_async(worker_type))


async def _record_worker_heartbeat_async(worker_type: str) -> None:
    """异步版本的心跳记录。"""
    from src.core.infrastructure.redis.client import get_async_redis_client
    from src.modules.agent.application.monitoring_service import MonitoringService

    try:
        async with get_async_redis_client(
            timeout=settings.REDIS_CLIENT_TIMEOUT_SEC
        ) as redis_client:
            monitoring = MonitoringService(redis_client)
            await monitoring.record_worker_heartbeat(worker_type)
            logger.debug(f"Heartbeat recorded for worker: {worker_type}")
    except Exception as e:
        logger.warning(f"Failed to record heartbeat: {e}")


async def _check_and_update_budget_async() -> None:
    """异步版本的预算检查。"""
    from src.core.domain.events import SimpleEventBus
    from src.core.infrastructure.database.session import get_async_session
    from src.core.infrastructure.redis.client import get_async_redis_client
    from src.modules.agent.infrastructure.mappers import BudgetDailyMapper
    from src.modules.agent.infrastructure.repositories import (
        PostgreSQLBudgetDailyRepository,
    )
    from src.modules.items.application.budget_service import BudgetService

    async with (
        get_async_redis_client(
            timeout=settings.REDIS_CLIENT_TIMEOUT_SEC
        ) as redis_client,
        get_async_session() as session,
    ):
        try:
            event_bus = SimpleEventBus()

            budget_service = BudgetService(redis_client)
            budget_repo = PostgreSQLBudgetDailyRepository(
                session, BudgetDailyMapper(), event_bus
            )

            # 获取 Redis 中的当前状态
            status = await budget_service.get_status()

            # 获取或创建数据库记录
            budget = await budget_repo.get_or_create_today()

            # 同步状态
            budget.embedding_tokens_est = status.embedding_tokens
            budget.judge_tokens_est = status.judge_tokens
            budget.usd_est = status.usd_est
            budget.embedding_disabled = status.embedding_disabled
            budget.judge_disabled = status.judge_disabled

            await budget_repo.update(budget)
            await session.commit()

            logger.info(
                f"Budget synced: date={budget.date}, "
                f"usd_est=${budget.usd_est:.4f}, "
                f"embedding_disabled={budget.embedding_disabled}"
            )

        except Exception as e:
            logger.exception(f"Error in check_and_update_budget: {e}")
            await session.rollback()
