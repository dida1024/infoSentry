"""Agent 编排器。

根据 AGENT_RUNTIME_SPEC.md 设计：
- 管理 Agent 运行生命周期
- 协调 Node 执行
- 记录运行结果
- 支持回放
"""

import math
import time
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from src.core.domain.events import EventBus
from src.modules.agent.application.logging_port import LoggingPort, ScoreTrace
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
    original_actions: list[dict[str, Any]] | None = Field(
        None, description="原始动作列表"
    )
    replayed_actions: list[dict[str, Any]] | None = Field(
        None, description="重放动作列表"
    )
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
        llm_service: Any | None = None,
        logging_port: LoggingPort | None = None,
    ):
        self.run_repo = run_repository
        self.tool_call_repo = tool_call_repository
        self.ledger_repo = ledger_repository
        self.tools = tools
        self.pipeline = pipeline
        self.event_bus = event_bus
        self.llm_service = llm_service
        self.logging_port = logging_port

    async def run_immediate(
        self,
        goal_id: str,
        item_id: str,
        match_score: float,
        match_features: dict[str, Any],
        match_reasons: dict[str, Any],
        goal_context: GoalContext | None = None,
        item_context: ItemContext | None = None,
        match_repository=None,
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
            if state.draft.llm_proposal or state.draft.push_worthiness:
                from src.core.config import settings

                agent_run.set_llm_used(settings.OPENAI_JUDGE_MODEL)

            # 若 LLM 判定为 SKIP，降低匹配度并记录链路评分
            if state.match:
                adjusted = state.draft.adjusted_score
                if adjusted is not None and match_repository:
                    await self._maybe_downgrade_match_score(
                        match_repository,
                        goal_id=goal_id,
                        item_id=item_id,
                        adjusted_score=adjusted,
                    )
                adjusted_score = adjusted if adjusted is not None else state.match.score
                self._log_score_trace(
                    trace=ScoreTrace(
                        goal_id=goal_id,
                        item_id=item_id,
                        trigger=state.trigger,
                        bucket=state.draft.preliminary_bucket.value
                        if state.draft.preliminary_bucket
                        else None,
                        match_score=state.match.score,
                        adjusted_score=adjusted_score,
                        thresholds=state.metadata.get("thresholds", {}),
                        llm_boundary=state.draft.llm_proposal,
                        push_worthiness=state.draft.push_worthiness,
                        boundary_fallback_reason=state.metadata.get(
                            "fallback_reason"
                        ),
                        push_worthiness_fallback_reason=state.draft.fallback_reason,
                        user_id=state.goal.user_id if state.goal else None,
                    )
                )

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
        goal_repository=None,
        item_repository=None,
        llm_service=None,
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
                if goal_repository:
                    goal = await goal_repository.get_by_id(goal_id)
                    if goal:
                        state.goal.user_id = goal.user_id
                        state.goal.name = goal.name
                        state.goal.description = goal.description
                # 1. 获取 Goal 的候选匹配（按分数排序，取 top N）
                from datetime import timedelta

                from src.modules.push.domain.entities import (
                    PushDecision,
                    PushDecisionRecord,
                    PushStatus,
                )

                since = datetime.now(UTC) - timedelta(hours=24)
                candidates = await match_repository.list_top_by_goal(
                    goal_id=goal_id,
                    min_score=settings.BATCH_THRESHOLD,
                    since=since,
                    limit=settings.BATCH_MAX_ITEMS * 2,  # 取多一些，后面过滤
                )

                # 2. 过滤已有决策的 items，按需填充到上限
                for candidate in candidates:
                    if actions_created >= settings.BATCH_MAX_ITEMS:
                        break

                    # 检查是否已有决策
                    import hashlib

                    dedupe_key_batch = hashlib.sha256(
                        f"{goal_id}:{candidate.item_id}:BATCH".encode()
                    ).hexdigest()[:32]

                    existing = await decision_repository.get_by_dedupe_key(
                        dedupe_key_batch
                    )
                    if existing:
                        continue

                    # LLM 二次判定推送价值
                    llm = llm_service or self.llm_service
                    llm_result = None
                    fallback_reason = None
                    adjusted_score = candidate.match_score
                    item_title = ""
                    item_snippet = ""
                    if item_repository:
                        item = await item_repository.get_by_id(candidate.item_id)
                        if item:
                            item_title = item.title
                            item_snippet = item.snippet or ""
                        else:
                            fallback_reason = "item_not_found"
                            llm = None
                    if llm:
                        llm_result, fallback_reason = await llm.judge_push_worthiness(
                            prompt=None,
                            goal_description=state.goal.description
                            if state.goal
                            else "",
                            item_title=item_title,
                            item_snippet=item_snippet,
                            match_score=candidate.match_score,
                            match_reasons=candidate.reasons_json,
                            user_id=state.goal.user_id if state.goal else None,
                        )
                    else:
                        fallback_reason = fallback_reason or "no_llm_service"

                    decision_type = PushDecision.BATCH
                    decision_status = None
                    decision_reason = "批量推送窗口匹配"
                    if llm_result:
                        if llm_result.label == "SKIP":
                            adjusted_score = math.nextafter(
                                settings.DIGEST_MIN_SCORE, 0.0
                            )
                            decision_type = PushDecision.IGNORE
                            decision_status = PushStatus.SKIPPED
                            decision_reason = f"LLM判定不值得推送：{llm_result.reason}"
                            await self._maybe_downgrade_match_score(
                                match_repository,
                                goal_id=goal_id,
                                item_id=candidate.item_id,
                                adjusted_score=adjusted_score,
                            )
                        else:
                            adjusted_score = candidate.match_score

                    score_trace = {
                        "match_score": candidate.match_score,
                        "adjusted_score": adjusted_score,
                        "thresholds": {
                            "batch_threshold": settings.BATCH_THRESHOLD,
                            "digest_min_score": settings.DIGEST_MIN_SCORE,
                        },
                        "llm": {
                            "push_worthiness": llm_result.model_dump()
                            if llm_result
                            else None,
                            "fallback_reason": fallback_reason,
                        },
                    }

                    dedupe_key = dedupe_key_batch
                    if decision_type == PushDecision.IGNORE:
                        dedupe_key = hashlib.sha256(
                            f"{goal_id}:{candidate.item_id}:IGNORE".encode()
                        ).hexdigest()[:32]
                        existing_ignore = await decision_repository.get_by_dedupe_key(
                            dedupe_key
                        )
                        if existing_ignore:
                            continue

                    # 3. 创建决策（通过工具，确保记账与审计）
                    reason_json = {
                        "reason": decision_reason,
                        "match_score": candidate.match_score,
                        "match_features": candidate.features_json,
                        "match_reasons": candidate.reasons_json,
                        "score_trace": score_trace,
                        "window_time": window_time,
                    }
                    emit_result = await self.tools.call(
                        "emit_decision",
                        goal_id=goal_id,
                        item_id=candidate.item_id,
                        decision=decision_type.value,
                        reason_json=reason_json,
                        dedupe_key=dedupe_key,
                        run_id=state.run_id,
                        status=decision_status.value if decision_status else None,
                    )
                    if not emit_result.success:
                        logger.warning(
                            "Emit decision failed in batch window",
                            goal_id=goal_id,
                            item_id=candidate.item_id,
                            error=emit_result.error,
                        )
                        continue
                    if decision_type == PushDecision.BATCH:
                        actions_created += 1

                    # 记录到 state actions
                    state.actions.append(
                        ActionProposal(
                            action_type="EMIT_DECISION",
                            decision=decision_type.value,
                            goal_id=goal_id,
                            item_id=candidate.item_id,
                            reason=decision_reason,
                            dedupe_key=dedupe_key,
                        )
                    )

                    # 记录评分链路
                    self._log_score_trace(
                        trace=ScoreTrace(
                            goal_id=goal_id,
                            item_id=candidate.item_id,
                            trigger=state.trigger,
                            bucket=decision_type.value,
                            match_score=candidate.match_score,
                            adjusted_score=adjusted_score,
                            thresholds=score_trace["thresholds"],
                            llm_boundary=None,
                            push_worthiness=score_trace["llm"]["push_worthiness"],
                            boundary_fallback_reason=None,
                            push_worthiness_fallback_reason=fallback_reason,
                            user_id=state.goal.user_id if state.goal else None,
                        )
                    )

            latency_ms = int((time.time() - start_time) * 1000)
            agent_run.mark_success(
                output=state.to_output_snapshot(),
                actions=[a.model_dump() for a in state.actions],
                latency_ms=latency_ms,
            )
            await self.run_repo.update(agent_run)

            for call_record in self.tools.get_call_records():
                await self.tool_call_repo.create(call_record)

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
        goal_repository=None,
        item_repository=None,
        llm_service=None,
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
                if goal_repository:
                    goal = await goal_repository.get_by_id(goal_id)
                    if goal:
                        state.goal.user_id = goal.user_id
                        state.goal.name = goal.name
                        state.goal.description = goal.description
                # 1. 获取过去 24 小时的候选（按分数排序）
                from datetime import timedelta

                from src.modules.push.domain.entities import (
                    PushDecision,
                    PushDecisionRecord,
                    PushStatus,
                )

                since = datetime.now(UTC) - timedelta(hours=24)
                candidates = await match_repository.list_top_by_goal(
                    goal_id=goal_id,
                    min_score=settings.DIGEST_MIN_SCORE,
                    since=since,
                    limit=settings.DIGEST_MAX_ITEMS_PER_GOAL * 2,  # 取多一些，后面过滤
                )

                # 2. 过滤已有 IMMEDIATE/BATCH 决策的 items，创建 DIGEST 决策
                for candidate in candidates:
                    if actions_created >= settings.DIGEST_MAX_ITEMS_PER_GOAL:
                        break

                    import hashlib

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

                    # LLM 二次判定推送价值
                    llm = llm_service or self.llm_service
                    llm_result = None
                    fallback_reason = None
                    adjusted_score = candidate.match_score
                    item_title = ""
                    item_snippet = ""
                    if item_repository:
                        item = await item_repository.get_by_id(candidate.item_id)
                        if item:
                            item_title = item.title
                            item_snippet = item.snippet or ""
                        else:
                            fallback_reason = "item_not_found"
                            llm = None
                    if llm:
                        llm_result, fallback_reason = await llm.judge_push_worthiness(
                            prompt=None,
                            goal_description=state.goal.description
                            if state.goal
                            else "",
                            item_title=item_title,
                            item_snippet=item_snippet,
                            match_score=candidate.match_score,
                            match_reasons=candidate.reasons_json,
                            user_id=state.goal.user_id if state.goal else None,
                        )
                    else:
                        fallback_reason = fallback_reason or "no_llm_service"

                    decision_type = PushDecision.DIGEST
                    decision_status = None
                    decision_reason = "每日摘要匹配"
                    if llm_result:
                        if llm_result.label == "SKIP":
                            adjusted_score = math.nextafter(
                                settings.DIGEST_MIN_SCORE, 0.0
                            )
                            decision_type = PushDecision.IGNORE
                            decision_status = PushStatus.SKIPPED
                            decision_reason = f"LLM判定不值得推送：{llm_result.reason}"
                            await self._maybe_downgrade_match_score(
                                match_repository,
                                goal_id=goal_id,
                                item_id=candidate.item_id,
                                adjusted_score=adjusted_score,
                            )
                        else:
                            adjusted_score = candidate.match_score

                    score_trace = {
                        "match_score": candidate.match_score,
                        "adjusted_score": adjusted_score,
                        "thresholds": {
                            "digest_min_score": settings.DIGEST_MIN_SCORE,
                        },
                        "llm": {
                            "push_worthiness": llm_result.model_dump()
                            if llm_result
                            else None,
                            "fallback_reason": fallback_reason,
                        },
                    }

                    dedupe_key = dedupe_key_digest
                    if decision_type == PushDecision.IGNORE:
                        dedupe_key = hashlib.sha256(
                            f"{goal_id}:{candidate.item_id}:IGNORE".encode()
                        ).hexdigest()[:32]
                        existing_ignore = await decision_repository.get_by_dedupe_key(
                            dedupe_key
                        )
                        if existing_ignore:
                            continue

                    # 3. 创建决策（通过工具，确保记账与审计）
                    reason_json = {
                        "reason": decision_reason,
                        "match_score": candidate.match_score,
                        "match_features": candidate.features_json,
                        "match_reasons": candidate.reasons_json,
                        "score_trace": score_trace,
                    }
                    emit_result = await self.tools.call(
                        "emit_decision",
                        goal_id=goal_id,
                        item_id=candidate.item_id,
                        decision=decision_type.value,
                        reason_json=reason_json,
                        dedupe_key=dedupe_key,
                        run_id=state.run_id,
                        status=decision_status.value if decision_status else None,
                    )
                    if not emit_result.success:
                        logger.warning(
                            "Emit decision failed in digest run",
                            goal_id=goal_id,
                            item_id=candidate.item_id,
                            error=emit_result.error,
                        )
                        continue
                    if decision_type == PushDecision.DIGEST:
                        actions_created += 1

                    # 记录到 state actions
                    state.actions.append(
                        ActionProposal(
                            action_type="EMIT_DECISION",
                            decision=decision_type.value,
                            goal_id=goal_id,
                            item_id=candidate.item_id,
                            reason=decision_reason,
                            dedupe_key=dedupe_key,
                        )
                    )

                    # 记录评分链路
                    self._log_score_trace(
                        trace=ScoreTrace(
                            goal_id=goal_id,
                            item_id=candidate.item_id,
                            trigger=state.trigger,
                            bucket=decision_type.value,
                            match_score=candidate.match_score,
                            adjusted_score=adjusted_score,
                            thresholds=score_trace["thresholds"],
                            llm_boundary=None,
                            push_worthiness=score_trace["llm"]["push_worthiness"],
                            boundary_fallback_reason=None,
                            push_worthiness_fallback_reason=fallback_reason,
                            user_id=state.goal.user_id if state.goal else None,
                        )
                    )

            latency_ms = int((time.time() - start_time) * 1000)
            agent_run.mark_success(
                output=state.to_output_snapshot(),
                actions=[a.model_dump() for a in state.actions],
                latency_ms=latency_ms,
            )
            await self.run_repo.update(agent_run)

            for call_record in self.tools.get_call_records():
                await self.tool_call_repo.create(call_record)

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

    async def _maybe_downgrade_match_score(
        self,
        match_repository,
        *,
        goal_id: str,
        item_id: str,
        adjusted_score: float,
    ) -> None:
        """降低匹配分数到阈值以下，避免再次推送。"""
        from src.core.config import settings

        if adjusted_score >= settings.DIGEST_MIN_SCORE:
            return

        match_record = await match_repository.get_by_goal_and_item(goal_id, item_id)
        if not match_record:
            logger.warning(
                f"Match record not found for downgrade: goal={goal_id}, item={item_id}"
            )
            return

        match_record.update_score(
            adjusted_score,
            match_record.features_json,
            match_record.reasons_json,
        )
        await match_repository.update(match_record)

    def _log_score_trace(self, *, trace: ScoreTrace) -> None:
        """记录评分链路到业务事件日志。"""
        if self.logging_port:
            self.logging_port.log_score_trace(trace)

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
            error=None,
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
        for i, (orig, repl) in enumerate(zip(original, replayed, strict=True)):
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
