"""Agent Tool Registry。

根据 AGENT_RUNTIME_SPEC.md 第 4 节设计，包含：
- 只读工具：get_goal_context, get_item, get_history, check_budget
- 写工具：emit_decision, enqueue_email, record_tool_call
- 工具调用记录
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from loguru import logger

from src.core.config import settings
from src.modules.agent.domain.entities import (
    AgentToolCall,
    ToolCallStatus,
)

T = TypeVar("T")


@dataclass
class ToolResult:
    """工具调用结果。"""

    success: bool
    data: Any = None
    error: str | None = None
    latency_ms: int = 0


class BaseTool(ABC):
    """工具基类。"""

    name: str = "base_tool"
    description: str = ""
    is_write: bool = False  # 是否是写操作

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具。"""
        pass


class ToolRegistry:
    """工具注册表。

    管理所有可用工具，并提供统一的调用接口。
    自动记录工具调用到 agent_tool_calls。
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._call_records: list[AgentToolCall] = []
        self._run_id: str | None = None

    def set_run_id(self, run_id: str) -> None:
        """设置当前运行 ID。"""
        self._run_id = run_id
        self._call_records = []

    def register(self, tool: BaseTool) -> None:
        """注册工具。"""
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get(self, name: str) -> BaseTool | None:
        """获取工具。"""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """列出所有工具名称。"""
        return list(self._tools.keys())

    async def call(self, name: str, **kwargs) -> ToolResult:
        """调用工具并记录。"""
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool not found: {name}")

        start_time = time.time()

        try:
            result = await tool.execute(**kwargs)
            latency_ms = int((time.time() - start_time) * 1000)
            result.latency_ms = latency_ms

            # 记录调用
            if self._run_id:
                self._record_call(
                    tool_name=name,
                    input_json=self._sanitize_input(kwargs),
                    output_json=self._sanitize_output(result),
                    status=ToolCallStatus.SUCCESS
                    if result.success
                    else ToolCallStatus.ERROR,
                    latency_ms=latency_ms,
                )

            return result

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"Tool {name} failed: {e}")

            if self._run_id:
                self._record_call(
                    tool_name=name,
                    input_json=self._sanitize_input(kwargs),
                    output_json={"error": str(e)},
                    status=ToolCallStatus.ERROR,
                    latency_ms=latency_ms,
                )

            return ToolResult(success=False, error=str(e), latency_ms=latency_ms)

    def _record_call(
        self,
        tool_name: str,
        input_json: dict[str, Any],
        output_json: dict[str, Any],
        status: ToolCallStatus,
        latency_ms: int,
    ) -> None:
        """记录工具调用。"""
        record = AgentToolCall(
            run_id=self._run_id,
            tool_name=tool_name,
            input_json=input_json,
            output_json=output_json,
            status=status,
            latency_ms=latency_ms,
        )
        self._call_records.append(record)

    def get_call_records(self) -> list[AgentToolCall]:
        """获取所有调用记录。"""
        return self._call_records

    def _sanitize_input(self, data: dict[str, Any]) -> dict[str, Any]:
        """脱敏输入数据。"""
        # 移除敏感字段
        sanitized = {}
        for key, value in data.items():
            if key in ("password", "token", "api_key", "secret"):
                sanitized[key] = "***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_input(value)
            else:
                sanitized[key] = value
        return sanitized

    def _sanitize_output(self, result: ToolResult) -> dict[str, Any]:
        """脱敏输出数据。"""
        return {
            "success": result.success,
            "error": result.error,
            "latency_ms": result.latency_ms,
            # 只保留部分数据，避免过大
            "data_type": type(result.data).__name__ if result.data else None,
        }


# ============================================
# 具体工具实现
# ============================================


class GetGoalContextTool(BaseTool):
    """获取 Goal 上下文。"""

    name = "get_goal_context"
    description = "获取指定 Goal 的完整上下文信息"
    is_write = False

    def __init__(self, goal_repository, term_repository, blocked_source_repo=None):
        self.goal_repo = goal_repository
        self.term_repo = term_repository
        self.blocked_source_repo = blocked_source_repo

    async def execute(self, goal_id: str, **kwargs) -> ToolResult:
        """执行获取 Goal 上下文。"""
        from src.modules.agent.application.state import GoalContext
        from src.modules.goals.domain.entities import TermType

        goal = await self.goal_repo.get_by_id(goal_id)
        if not goal:
            return ToolResult(success=False, error=f"Goal not found: {goal_id}")

        # 获取 priority_terms
        terms = await self.term_repo.list_by_goal(goal_id)
        must_terms = [t.term for t in terms if t.term_type == TermType.MUST]
        negative_terms = [t.term for t in terms if t.term_type == TermType.NEGATIVE]

        # 获取 blocked_sources
        blocked_sources = []
        if self.blocked_source_repo:
            blocked = await self.blocked_source_repo.list_by_goal(goal_id)
            blocked_sources = [b.source_id for b in blocked]

        context = GoalContext(
            goal_id=goal.id,
            user_id=goal.user_id,
            name=goal.name,
            description=goal.description,
            priority_mode=goal.priority_mode.value,
            must_terms=must_terms,
            negative_terms=negative_terms,
            blocked_sources=blocked_sources,
            time_window_days=goal.time_window_days,
        )

        return ToolResult(success=True, data=context)


class GetItemTool(BaseTool):
    """获取 Item 信息。"""

    name = "get_item"
    description = "获取指定 Item 的详细信息"
    is_write = False

    def __init__(self, item_repository, source_repository=None):
        self.item_repo = item_repository
        self.source_repo = source_repository

    async def execute(self, item_id: str, **kwargs) -> ToolResult:
        """执行获取 Item。"""
        from src.modules.agent.application.state import ItemContext

        item = await self.item_repo.get_by_id(item_id)
        if not item:
            return ToolResult(success=False, error=f"Item not found: {item_id}")

        source_name = None
        if self.source_repo:
            source = await self.source_repo.get_by_id(item.source_id)
            source_name = source.name if source else None

        context = ItemContext(
            item_id=item.id,
            source_id=item.source_id,
            source_name=source_name,
            title=item.title,
            url=item.url,
            snippet=item.snippet,
            published_at=item.published_at,
        )

        return ToolResult(success=True, data=context)


class GetHistoryTool(BaseTool):
    """获取历史上下文。"""

    name = "get_history"
    description = "获取 Goal 的历史决策和反馈"
    is_write = False

    def __init__(
        self, decision_repository=None, click_repository=None, feedback_repository=None
    ):
        self.decision_repo = decision_repository
        self.click_repo = click_repository
        self.feedback_repo = feedback_repository

    async def execute(
        self, goal_id: str, window_hours: int = 24, **kwargs
    ) -> ToolResult:
        """执行获取历史。"""
        from src.modules.agent.application.state import HistoryContext

        history = HistoryContext()

        # 获取最近决策
        if self.decision_repo:
            since = datetime.now(UTC) - timedelta(hours=window_hours)
            decisions, _ = await self.decision_repo.list_by_goal(
                goal_id=goal_id, since=since, page_size=20
            )
            history.recent_decisions = [
                {
                    "item_id": d.item_id,
                    "decision": d.decision,
                    "created_at": d.created_at.isoformat(),
                }
                for d in decisions
            ]

        # 获取最近点击
        if self.click_repo:
            clicks = await self.click_repo.list_by_goal(goal_id, limit=10)
            history.recent_clicks = [
                {"item_id": c.item_id, "clicked_at": c.created_at.isoformat()}
                for c in clicks
            ]

        # 获取反馈统计
        if self.feedback_repo:
            stats = await self.feedback_repo.get_stats_by_goal(goal_id)
            history.feedback_stats = stats

        return ToolResult(success=True, data=history)


class CheckBudgetTool(BaseTool):
    """检查预算状态。"""

    name = "check_budget"
    description = "检查当前预算状态"
    is_write = False

    def __init__(self, budget_service):
        self.budget_service = budget_service

    async def execute(self, **kwargs) -> ToolResult:
        """执行检查预算。"""
        from src.modules.agent.application.state import BudgetContext

        status = await self.budget_service.get_status()

        context = BudgetContext(
            embedding_disabled=status.embedding_disabled,
            judge_disabled=status.judge_disabled,
            usd_est_today=status.usd_est,
            daily_limit=settings.DAILY_USD_BUDGET,
        )

        return ToolResult(success=True, data=context)


class EmitDecisionTool(BaseTool):
    """发出推送决策。"""

    name = "emit_decision"
    description = "创建推送决策记录"
    is_write = True

    def __init__(self, decision_repository, action_ledger_repo=None):
        self.decision_repo = decision_repository
        self.ledger_repo = action_ledger_repo

    async def execute(
        self,
        goal_id: str,
        item_id: str,
        decision: str,
        reason_json: dict[str, Any],
        dedupe_key: str,
        run_id: str | None = None,
        **kwargs,
    ) -> ToolResult:
        """执行发出决策。"""
        from src.modules.push.domain.entities import (
            PushDecision as PushDecisionEnum,
            PushDecisionRecord,
        )

        # 检查幂等
        existing = await self.decision_repo.get_by_dedupe_key(dedupe_key)
        if existing:
            logger.info(f"Decision already exists: {dedupe_key}")
            return ToolResult(
                success=True, data={"id": existing.id, "deduplicated": True}
            )

        # 创建决策
        push_decision = PushDecisionRecord(
            goal_id=goal_id,
            item_id=item_id,
            decision=PushDecisionEnum(decision),
            reason_json=reason_json,
            dedupe_key=dedupe_key,
        )

        created = await self.decision_repo.create(push_decision)

        # 记录到 action ledger
        if self.ledger_repo and run_id:
            from src.modules.agent.domain.entities import ActionType, AgentActionLedger

            ledger = AgentActionLedger(
                run_id=run_id,
                action_type=ActionType.EMIT_DECISION,
                payload_json={
                    "decision_id": created.id,
                    "goal_id": goal_id,
                    "item_id": item_id,
                    "decision": decision,
                },
            )
            await self.ledger_repo.create(ledger)

        return ToolResult(success=True, data={"id": created.id, "deduplicated": False})


class EnqueueEmailTool(BaseTool):
    """加入邮件队列。"""

    name = "enqueue_email"
    description = "将决策加入邮件发送队列"
    is_write = True

    def __init__(self, redis_client=None, ledger_repo=None):
        self.redis = redis_client
        self.ledger_repo = ledger_repo

    async def execute(
        self,
        decision_ids: list[str],
        channel: str = "email",
        run_id: str | None = None,
        **kwargs,
    ) -> ToolResult:
        """执行加入邮件队列。"""
        # 写入 Redis 队列或直接触发 Celery 任务
        if self.redis:
            from src.core.infrastructure.redis.keys import RedisKeys

            key = RedisKeys.immediate_buffer("email", channel)
            for decision_id in decision_ids:
                await self.redis.lpush(key, decision_id)

        # 记录到 action ledger
        if self.ledger_repo and run_id:
            from src.modules.agent.domain.entities import ActionType, AgentActionLedger

            ledger = AgentActionLedger(
                run_id=run_id,
                action_type=ActionType.ENQUEUE_EMAIL,
                payload_json={
                    "decision_ids": decision_ids,
                    "channel": channel,
                },
            )
            await self.ledger_repo.create(ledger)

        return ToolResult(success=True, data={"queued": len(decision_ids)})


def create_default_registry(
    goal_repository=None,
    term_repository=None,
    item_repository=None,
    source_repository=None,
    decision_repository=None,
    budget_service=None,
    redis_client=None,
    ledger_repo=None,
    blocked_source_repo=None,
    click_repository=None,
    feedback_repository=None,
    **kwargs,
) -> ToolRegistry:
    """创建默认工具注册表。"""
    registry = ToolRegistry()

    if goal_repository and term_repository:
        registry.register(
            GetGoalContextTool(goal_repository, term_repository, blocked_source_repo)
        )

    if item_repository:
        registry.register(GetItemTool(item_repository, source_repository))

    if decision_repository:
        registry.register(
            GetHistoryTool(decision_repository, click_repository, feedback_repository)
        )

    if budget_service:
        registry.register(CheckBudgetTool(budget_service))

    if decision_repository:
        registry.register(EmitDecisionTool(decision_repository, ledger_repo))

    if redis_client:
        registry.register(EnqueueEmailTool(redis_client, ledger_repo))

    return registry
