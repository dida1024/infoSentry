"""Agent 编排器。

根据 AGENT_RUNTIME_SPEC.md 设计：
- 管理 Agent 运行生命周期
- 协调 Node 执行
- 记录运行结果
- 支持回放
"""

import time
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from src.core.domain.events import EventBus
from src.modules.agent.application.nodes import (
    NodePipeline,
    create_immediate_pipeline,
)
from src.modules.agent.application.state import (
    ActionProposal,
    AgentState,
    GoalContext,
    ItemContext,
    MatchContext,
)
from src.modules.agent.application.tools import ToolRegistry
from src.modules.agent.domain.entities import (
    AgentRun,
    AgentRunStatus,
    AgentTrigger,
)
from src.modules.agent.domain.repository import (
    AgentActionLedgerRepository,
    AgentRunRepository,
    AgentToolCallRepository,
)


class ReplayResult(BaseModel):
    """Agent 运行回放结果。"""

    run_id: str = Field(..., description="运行 ID")
    original_status: str | None = Field(None, description="原始运行状态")
    original_actions: list[dict[str, Any]] | None = Field(None, description="原始动作列表")
    replayed_actions: list[dict[str, Any]] | None = Field(None, description="重放动作列表")
    diff: list[dict[str, Any]] | None = Field(None, description="动作差异")
    tool_calls_count: int | None = Field(None, description="工具调用次数", ge=0)
    ledger_entries_count: int | None = Field(None, description="账本记录数", ge=0)
    error: str | None = Field(None, description="错误信息")

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于 API 响应）。"""
        return self.model_dump(mode="json", exclude_none=False)


class AgentOrchestrator:
    """Agent 编排器。

    职责：
    - 创建和管理 AgentRun
    - 执行 Node Pipeline
    - 保存运行结果
    - 支持回放
    """

    def __init__(
        self,
        run_repository: AgentRunRepository,
        tool_call_repository: AgentToolCallRepository,
        ledger_repository: AgentActionLedgerRepository,
        tools: ToolRegistry,
        pipeline: NodePipeline | None = None,
        event_bus: EventBus | None = None,
    ):
        self.run_repo = run_repository
        self.tool_call_repo = tool_call_repository
        self.ledger_repo = ledger_repository
        self.tools = tools
        self.pipeline = pipeline
        self.event_bus = event_bus

    async def run_immediate(
        self,
        goal_id: str,
        item_id: str,
        match_score: float,
        match_features: dict[str, Any],
        match_reasons: dict[str, Any],
        goal_context: GoalContext | None = None,
        item_context: ItemContext | None = None,
    ) -> AgentRun:
        """执行 Immediate 路径的 Agent 决策。

        Args:
            goal_id: Goal ID
            item_id: Item ID
            match_score: 匹配分数
            match_features: 匹配特征
            match_reasons: 匹配原因
            goal_context: Goal 上下文（可选，会自动加载）
            item_context: Item 上下文（可选，会自动加载）

        Returns:
            AgentRun 记录
        """
        start_time = time.time()

        # 创建初始状态
        state = AgentState(
            trigger="MatchComputed",
            goal=goal_context
            or GoalContext(
                goal_id=goal_id,
                user_id="",
                name="",
                description="",
                priority_mode="SOFT",
            ),
            item=item_context
            or ItemContext(
                item_id=item_id,
                source_id="",
                title="",
                url="",
            ),
            match=MatchContext(
                score=match_score,
                features=match_features,
                reasons=match_reasons,
            ),
        )

        # 设置工具的 run_id
        self.tools.set_run_id(state.run_id)

        # 创建 AgentRun 记录
        agent_run = AgentRun(
            id=state.run_id,
            trigger=AgentTrigger.MATCH_COMPUTED,
            goal_id=goal_id,
            status=AgentRunStatus.RUNNING,
            input_snapshot_json=state.to_input_snapshot(),
        )

        try:
            # 保存初始记录
            agent_run = await self.run_repo.create(agent_run)

            # 执行 Pipeline
            if self.pipeline:
                state = await self.pipeline.run(state)
            else:
                logger.warning("No pipeline configured, using default")
                default_pipeline = create_immediate_pipeline(self.tools)
                state = await default_pipeline.run(state)

            # 计算耗时
            latency_ms = int((time.time() - start_time) * 1000)

            # 判断是否使用了 LLM
            if state.draft.llm_proposal:
                from src.core.config import settings

                agent_run.set_llm_used(settings.OPENAI_JUDGE_MODEL)

            # 标记成功
            agent_run.mark_success(
                output=state.to_output_snapshot(),
                actions=[a.model_dump() for a in state.actions],
                latency_ms=latency_ms,
            )

            # 更新记录
            agent_run = await self.run_repo.update(agent_run)

            # 保存工具调用记录
            for call_record in self.tools.get_call_records():
                await self.tool_call_repo.create(call_record)

            logger.info(
                f"Agent run completed: {agent_run.id}, "
                f"status={agent_run.status}, "
                f"actions={len(state.actions)}, "
                f"latency={latency_ms}ms"
            )

            return agent_run

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"Agent run failed: {e}")

            agent_run.mark_error(str(e), latency_ms)
            await self.run_repo.update(agent_run)

            return agent_run

    async def run_batch_window(
        self,
        goal_id: str,
        window_time: str,
        match_repository=None,
        decision_repository=None,
    ) -> AgentRun:
        """执行 Batch 窗口的 Agent 决策。

        Args:
            goal_id: Goal ID
            window_time: 窗口时间（HH:MM）
            match_repository: GoalItemMatch repository（可选）
            decision_repository: PushDecision repository（可选）

        Returns:
            AgentRun 记录
        """
        from src.core.config import settings

        start_time = time.time()

        state = AgentState(
            trigger="BatchWindowTick",
            goal=GoalContext(
                goal_id=goal_id,
                user_id="",
                name="",
                description="",
                priority_mode="SOFT",
            ),
            metadata={"window_time": window_time},
        )

        self.tools.set_run_id(state.run_id)

        agent_run = AgentRun(
            id=state.run_id,
            trigger=AgentTrigger.BATCH_WINDOW_TICK,
            goal_id=goal_id,
            status=AgentRunStatus.RUNNING,
            input_snapshot_json=state.to_input_snapshot(),
        )

        try:
            agent_run = await self.run_repo.create(agent_run)

            actions_created = 0

            # 如果提供了 repositories，执行 Batch 逻辑
            if match_repository and decision_repository:
                # 1. 获取 Goal 的候选匹配（按分数排序，取 top N）
                from datetime import timedelta

                since = datetime.now(UTC) - timedelta(hours=24)
                candidates = await match_repository.list_top_by_goal(
                    goal_id=goal_id,
                    min_score=settings.BATCH_THRESHOLD,
                    since=since,
                    limit=settings.BATCH_MAX_ITEMS * 2,  # 取多一些，后面过滤
                )

                # 2. 过滤已有决策的 items
                for candidate in candidates[: settings.BATCH_MAX_ITEMS]:
                    # 检查是否已有决策
                    import hashlib

                    from src.modules.push.domain.entities import (
                        PushDecision,
                        PushDecisionRecord,
                    )

                    dedupe_key = hashlib.sha256(
                        f"{goal_id}:{candidate.item_id}:BATCH".encode()
                    ).hexdigest()[:32]

                    existing = await decision_repository.get_by_dedupe_key(dedupe_key)
                    if existing:
                        continue

                    # 3. 创建 BATCH 决策
                    decision = PushDecisionRecord(
                        goal_id=goal_id,
                        item_id=candidate.item_id,
                        decision=PushDecision.BATCH,
                        reason_json={
                            "reason": "批量推送窗口匹配",
                            "match_score": candidate.match_score,
                            "features": candidate.features_json,
                            "window_time": window_time,
                        },
                        dedupe_key=dedupe_key,
                    )
                    await decision_repository.create(decision)
                    actions_created += 1

                    # 记录到 state actions
                    state.actions.append(
                        ActionProposal(
                            action_type="EMIT_DECISION",
                            decision="BATCH",
                            goal_id=goal_id,
                            item_id=candidate.item_id,
                            reason="批量推送窗口匹配",
                            dedupe_key=dedupe_key,
                        )
                    )

            latency_ms = int((time.time() - start_time) * 1000)
            agent_run.mark_success(
                output=state.to_output_snapshot(),
                actions=[a.model_dump() for a in state.actions],
                latency_ms=latency_ms,
            )
            await self.run_repo.update(agent_run)

            logger.info(
                f"Batch window run completed: {agent_run.id}, "
                f"created {actions_created} decisions"
            )

            return agent_run

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            agent_run.mark_error(str(e), latency_ms)
            await self.run_repo.update(agent_run)
            logger.exception(f"Batch window run failed: {e}")
            return agent_run

    async def run_digest(
        self,
        goal_id: str,
        match_repository=None,
        decision_repository=None,
    ) -> AgentRun:
        """执行 Digest 的 Agent 决策。

        Args:
            goal_id: Goal ID
            match_repository: GoalItemMatch repository（可选）
            decision_repository: PushDecision repository（可选）

        Returns:
            AgentRun 记录
        """
        from src.core.config import settings

        start_time = time.time()

        state = AgentState(
            trigger="DigestTick",
            goal=GoalContext(
                goal_id=goal_id,
                user_id="",
                name="",
                description="",
                priority_mode="SOFT",
            ),
        )

        self.tools.set_run_id(state.run_id)

        agent_run = AgentRun(
            id=state.run_id,
            trigger=AgentTrigger.DIGEST_TICK,
            goal_id=goal_id,
            status=AgentRunStatus.RUNNING,
            input_snapshot_json=state.to_input_snapshot(),
        )

        try:
            agent_run = await self.run_repo.create(agent_run)

            actions_created = 0

            # 如果提供了 repositories，执行 Digest 逻辑
            if match_repository and decision_repository:
                # 1. 获取过去 24 小时的候选（按分数排序）
                from datetime import timedelta

                since = datetime.now(UTC) - timedelta(hours=24)
                candidates = await match_repository.list_top_by_goal(
                    goal_id=goal_id,
                    min_score=settings.DIGEST_MIN_SCORE,
                    since=since,
                    limit=settings.DIGEST_MAX_ITEMS_PER_GOAL * 2,  # 取多一些，后面过滤
                )

                # 2. 过滤已有 IMMEDIATE/BATCH 决策的 items，创建 DIGEST 决策
                for candidate in candidates[: settings.DIGEST_MAX_ITEMS_PER_GOAL]:
                    import hashlib

                    from src.modules.push.domain.entities import (
                        PushDecision,
                        PushDecisionRecord,
                    )

                    # 检查是否已有任何类型的决策
                    dedupe_key_digest = hashlib.sha256(
                        f"{goal_id}:{candidate.item_id}:DIGEST".encode()
                    ).hexdigest()[:32]

                    existing = await decision_repository.get_by_dedupe_key(
                        dedupe_key_digest
                    )
                    if existing:
                        continue

                    # 也检查是否已有 IMMEDIATE 或 BATCH 决策
                    for dtype in ["IMMEDIATE", "BATCH"]:
                        other_key = hashlib.sha256(
                            f"{goal_id}:{candidate.item_id}:{dtype}".encode()
                        ).hexdigest()[:32]
                        if await decision_repository.get_by_dedupe_key(other_key):
                            continue

                    # 3. 创建 DIGEST 决策
                    decision = PushDecisionRecord(
                        goal_id=goal_id,
                        item_id=candidate.item_id,
                        decision=PushDecision.DIGEST,
                        reason_json={
                            "reason": "每日摘要匹配",
                            "match_score": candidate.match_score,
                            "features": candidate.features_json,
                        },
                        dedupe_key=dedupe_key_digest,
                    )
                    await decision_repository.create(decision)
                    actions_created += 1

                    # 记录到 state actions
                    state.actions.append(
                        ActionProposal(
                            action_type="EMIT_DECISION",
                            decision="DIGEST",
                            goal_id=goal_id,
                            item_id=candidate.item_id,
                            reason="每日摘要匹配",
                            dedupe_key=dedupe_key_digest,
                        )
                    )

            latency_ms = int((time.time() - start_time) * 1000)
            agent_run.mark_success(
                output=state.to_output_snapshot(),
                actions=[a.model_dump() for a in state.actions],
                latency_ms=latency_ms,
            )
            await self.run_repo.update(agent_run)

            logger.info(
                f"Digest run completed: {agent_run.id}, "
                f"created {actions_created} decisions"
            )

            return agent_run

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            agent_run.mark_error(str(e), latency_ms)
            await self.run_repo.update(agent_run)
            logger.exception(f"Digest run failed: {e}")
            return agent_run

    async def replay(self, run_id: str) -> ReplayResult:
        """回放指定的 Agent 运行。

        Args:
            run_id: 运行 ID

        Returns:
            回放结果，包含原始动作、重放动作和差异
        """
        # 获取原始运行记录
        original_run = await self.run_repo.get_by_id(run_id)
        if not original_run:
            return ReplayResult(run_id=run_id, error=f"Run not found: {run_id}")

        # 获取原始工具调用
        tool_calls = await self.tool_call_repo.list_by_run(run_id)

        # 获取原始 action ledger
        ledger_entries = await self.ledger_repo.list_by_run(run_id)

        # 重建初始状态
        input_snapshot = original_run.input_snapshot_json
        state = AgentState(
            run_id=f"replay_{run_id}",
            trigger=input_snapshot.get("trigger", "MatchComputed"),
            goal=GoalContext(**input_snapshot["goal"])
            if input_snapshot.get("goal")
            else None,
            item=ItemContext(**input_snapshot["item"])
            if input_snapshot.get("item")
            else None,
            match=MatchContext(**input_snapshot["match"])
            if input_snapshot.get("match")
            else None,
        )

        # 重放 Pipeline
        if self.pipeline:
            replayed_state = await self.pipeline.run(state)
        else:
            default_pipeline = create_immediate_pipeline(self.tools)
            replayed_state = await default_pipeline.run(state)

        # 比较结果
        original_actions = original_run.final_actions_json
        replayed_actions = [a.model_dump() for a in replayed_state.actions]

        diff = self._compute_diff(original_actions, replayed_actions)

        return ReplayResult(
            run_id=run_id,
            original_status=original_run.status.value,
            original_actions=original_actions,
            replayed_actions=replayed_actions,
            diff=diff,
            tool_calls_count=len(tool_calls),
            ledger_entries_count=len(ledger_entries),
        )

    def _compute_diff(
        self,
        original: list[dict[str, Any]],
        replayed: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """计算动作差异。"""
        diff = []

        # 简单比较
        if len(original) != len(replayed):
            diff.append(
                {
                    "type": "count_mismatch",
                    "original_count": len(original),
                    "replayed_count": len(replayed),
                }
            )

        # 比较每个动作
        for i, (orig, repl) in enumerate(zip(original, replayed)):
            if orig.get("decision") != repl.get("decision"):
                diff.append(
                    {
                        "type": "decision_mismatch",
                        "index": i,
                        "original": orig.get("decision"),
                        "replayed": repl.get("decision"),
                    }
                )

        return diff
