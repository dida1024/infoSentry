"""Agent Node 实现。

根据 AGENT_RUNTIME_SPEC.md 第 5 节设计，包含：
- LoadContextNode: 加载上下文
- RuleGateNode: 规则守门
- BucketNode: 阈值分桶
- BoundaryJudgeNode: 边界 LLM 判别
- CoalesceNode: 合并窗口
- EmitActionsNode: 发出动作
"""

import hashlib
import math
import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from loguru import logger

from src.core.config import settings
from src.modules.agent.application.state import (
    DEFAULT_THRESHOLDS,
    ActionProposal,
    AgentState,
    BlockReason,
    DecisionBucket,
    ThresholdConfig,
)
from src.modules.agent.application.tools import ToolRegistry

if TYPE_CHECKING:
    from src.modules.agent.application.llm_service import BoundaryJudgeOutput


class BaseNode(ABC):
    """Node 基类。

    每个 Node：
    - 接收 AgentState
    - 返回修改后的 AgentState
    - 副作用只能通过 tools
    """

    name: str = "base_node"

    def __init__(self, tools: ToolRegistry | None = None):
        self.tools = tools

    @abstractmethod
    async def process(self, state: AgentState) -> AgentState:
        """处理状态。"""
        pass


class LoadContextNode(BaseNode):
    """加载上下文节点。

    使用工具加载：
    - Goal 上下文（含 must_terms, negative_terms, blocked_sources）
    - Item 上下文
    - 预算状态
    - 历史记录
    """

    name = "load_context"

    async def process(self, state: AgentState) -> AgentState:
        """加载所有必要的上下文。"""
        if not self.tools:
            logger.warning("LoadContextNode: No tools available")
            return state

        # 加载 Goal 上下文
        if state.goal and not state.goal.must_terms:
            result = await self.tools.call(
                "get_goal_context", goal_id=state.goal.goal_id
            )
            if result.success and result.data:
                state.goal = result.data

        # 加载预算状态
        budget_result = await self.tools.call("check_budget")
        if budget_result.success and budget_result.data:
            state.budget = budget_result.data

        logger.debug(f"LoadContextNode: Loaded context for run {state.run_id}")
        return state


class RuleGateNode(BaseNode):
    """规则守门节点。

    检查：
    - blocked_sources: 来源是否被屏蔽
    - negative_terms: 是否命中负面词
    - STRICT 模式: 是否命中 must_terms
    """

    name = "rule_gate"

    async def process(self, state: AgentState) -> AgentState:
        """执行规则守门。"""
        if not state.goal or not state.item:
            logger.warning("RuleGateNode: Missing goal or item")
            return state

        # 检查 blocked_sources
        if state.item.source_id in state.goal.blocked_sources:
            state.draft.blocked = True
            state.draft.block_reason = BlockReason.BLOCKED_SOURCE
            state.draft.block_details = f"Source {state.item.source_id} is blocked"
            logger.info(f"RuleGate: Blocked by source {state.item.source_id}")
            return state

        # 准备文本用于匹配
        text = self._get_searchable_text(state.item)
        text_lower = text.lower()

        # 检查 negative_terms
        for term in state.goal.negative_terms:
            if self._term_matches(term, text_lower):
                state.draft.blocked = True
                state.draft.block_reason = BlockReason.NEGATIVE_TERM
                state.draft.block_details = f"Matched negative term: {term}"
                logger.info(f"RuleGate: Blocked by negative term '{term}'")
                return state

        # 检查 STRICT 模式
        if state.goal.priority_mode == "STRICT" and state.goal.must_terms:
            has_hit = any(
                self._term_matches(term, text_lower) for term in state.goal.must_terms
            )
            if not has_hit:
                state.draft.blocked = True
                state.draft.block_reason = BlockReason.STRICT_NO_HIT
                state.draft.block_details = (
                    "STRICT mode requires at least one must_term hit"
                )
                logger.info("RuleGate: Blocked by STRICT mode (no must_term hit)")
                return state

        logger.debug(f"RuleGate: Passed for item {state.item.item_id}")
        return state

    def _get_searchable_text(self, item) -> str:
        """获取可搜索文本。"""
        parts = [item.title]
        if item.snippet:
            parts.append(item.snippet)
        return " ".join(parts)

    def _term_matches(self, term: str, text: str) -> bool:
        """检查词条是否匹配。

        对于英文使用词边界，对于中文使用简单包含匹配。
        """
        term_lower = term.lower()

        # 检查是否包含中文字符
        has_chinese = any("\u4e00" <= c <= "\u9fff" for c in term)

        if has_chinese:
            # 中文使用简单包含匹配
            return term_lower in text
        else:
            # 英文使用词边界匹配
            pattern = r"\b" + re.escape(term_lower) + r"\b"
            return bool(re.search(pattern, text))


class BucketNode(BaseNode):
    """阈值分桶节点。

    根据 match_score 分桶：
    - >= 0.93: IMMEDIATE
    - 0.88 ~ 0.93: BOUNDARY（进入 LLM）
    - 0.75 ~ 0.88: BATCH
    - < 0.75: IGNORE
    """

    name = "bucket"

    def __init__(
        self,
        tools: ToolRegistry | None = None,
        thresholds: ThresholdConfig | None = None,
    ):
        super().__init__(tools)
        self.thresholds = thresholds or DEFAULT_THRESHOLDS

    async def process(self, state: AgentState) -> AgentState:
        """执行分桶。"""
        # 如果已被阻止，直接返回
        if state.draft.blocked:
            logger.debug("BucketNode: Skipped (already blocked)")
            return state

        if not state.match:
            logger.warning("BucketNode: No match context")
            state.draft.preliminary_bucket = DecisionBucket.IGNORE
            return state

        score = state.match.score
        bucket = self.thresholds.get_bucket(score)
        state.draft.preliminary_bucket = bucket
        state.metadata.setdefault(
            "thresholds",
            {
                "immediate_threshold": self.thresholds.immediate_threshold,
                "boundary_lower": self.thresholds.boundary_lower,
                "batch_threshold": self.thresholds.batch_threshold,
            },
        )

        logger.info(f"BucketNode: score={score:.4f} -> {bucket.value}")
        return state


class BoundaryJudgeNode(BaseNode):
    """边界 LLM 判别节点。

    当分桶为 BOUNDARY 且 judge_disabled=False 时：
    - 调用 LLM 进行判别
    - 输出结构化 proposal
    - 失败时降级为 BATCH
    """

    name = "boundary_judge"

    def __init__(
        self,
        tools: ToolRegistry | None = None,
        llm_service: Any = None,
    ):
        super().__init__(tools)
        self.llm_service = llm_service

    async def process(self, state: AgentState) -> AgentState:
        """执行边界判别。"""
        # 如果已被阻止或不是 BOUNDARY，跳过
        if state.draft.blocked:
            return state

        if state.draft.preliminary_bucket != DecisionBucket.BOUNDARY:
            return state

        # 检查 judge 是否被禁用
        if state.budget.judge_disabled:
            logger.info("BoundaryJudge: Judge disabled, fallback to BATCH")
            state.draft.preliminary_bucket = DecisionBucket.BATCH
            state.metadata["fallback_reason"] = "judge_disabled"
            return state

        # 如果没有 LLM 服务，降级
        if not self.llm_service:
            logger.info("BoundaryJudge: No LLM service, fallback to BATCH")
            state.draft.preliminary_bucket = DecisionBucket.BATCH
            state.metadata["fallback_reason"] = "no_llm_service"
            return state

        # 调用 LLM
        try:
            proposal = await self._call_llm(state)

            if proposal:
                state.draft.llm_proposal = proposal.model_dump()
                state.draft.llm_confidence = proposal.confidence

                if proposal.label == "IMMEDIATE":
                    state.draft.preliminary_bucket = DecisionBucket.IMMEDIATE
                else:
                    state.draft.preliminary_bucket = DecisionBucket.BATCH

                logger.info(
                    f"BoundaryJudge: LLM decision={proposal.label}, "
                    f"confidence={state.draft.llm_confidence}"
                )
            else:
                # LLM 无响应，降级
                state.draft.preliminary_bucket = DecisionBucket.BATCH
                state.metadata["fallback_reason"] = "llm_no_response"

        except Exception as e:
            logger.exception(f"BoundaryJudge: LLM error: {e}")
            state.draft.preliminary_bucket = DecisionBucket.BATCH
            state.metadata["fallback_reason"] = f"llm_error: {str(e)}"

        return state

    async def _call_llm(self, state: AgentState) -> "BoundaryJudgeOutput | None":
        """调用 LLM 进行判别。

        Args:
            state: Agent 状态

        Returns:
            BoundaryJudgeOutput | None: LLM 判别结果或 None
        """
        if not self.llm_service:
            return None

        # 调用 LLM（prompt 由 LLMJudgeService 统一构建，避免重复/分散）
        result = await self.llm_service.judge_boundary(
            prompt=None,
            goal_description=state.goal.description if state.goal else "",
            item_title=state.item.title if state.item else "",
            item_snippet=state.item.snippet if state.item else "",
            match_score=state.match.score if state.match else 0,
            match_reasons=state.match.reasons if state.match else {},
            user_id=state.goal.user_id if state.goal else None,
        )

        return result


class CoalesceNode(BaseNode):
    """合并窗口节点。

    对于 IMMEDIATE 决策：
    - 将决策 ID 写入 Redis 5 分钟合并缓冲区
    - 最多 3 条/封
    """

    name = "coalesce"

    def __init__(self, tools: ToolRegistry | None = None, redis_client=None):
        super().__init__(tools)
        self.redis = redis_client

    async def process(self, state: AgentState) -> AgentState:
        """执行合并窗口。"""
        # 只处理 IMMEDIATE
        if state.draft.blocked:
            return state

        if state.draft.preliminary_bucket != DecisionBucket.IMMEDIATE:
            return state

        if not state.goal or not state.item:
            return state

        # 计算 5 分钟时间桶
        now = datetime.now(UTC)
        time_bucket = now.strftime("%Y%m%d%H") + str(now.minute // 5)

        # 写入 Redis 缓冲区
        if self.redis:
            from src.core.infrastructure.redis.keys import RedisKeys

            decision_id = self._extract_immediate_decision_id(state)
            if not decision_id:
                state.metadata["coalesce_skipped_reason"] = "missing_decision_id"
                logger.warning(
                    "Coalesce: Missing decision_id for immediate action, skipping"
                )
                return state

            buffer_key = RedisKeys.immediate_buffer(state.goal.goal_id, time_bucket)

            # 获取当前缓冲区大小
            current_size = await self.redis.llen(buffer_key)

            if current_size >= settings.IMMEDIATE_MAX_ITEMS:
                # 超过上限，不再合并
                logger.info(f"Coalesce: Buffer full ({current_size}), skipping")
                state.metadata["coalesce_skipped"] = True
            else:
                # 加入缓冲区
                await self.redis.rpush(buffer_key, decision_id)
                await self.redis.expire(buffer_key, 600)  # 10 分钟过期
                state.metadata["coalesce_buffer_key"] = buffer_key
                state.metadata["coalesce_decision_id"] = decision_id
                logger.debug(f"Coalesce: Added to buffer {buffer_key}")

        return state

    @staticmethod
    def _extract_immediate_decision_id(state: AgentState) -> str | None:
        """Extract decision id from emitted immediate action.

        Only non-deduplicated actions should be enqueued to avoid repeated buffering.
        """
        for action in reversed(state.actions):
            if action.action_type != "EMIT_DECISION":
                continue
            if action.decision != DecisionBucket.IMMEDIATE.value:
                continue

            decision_id = action.metadata.get("decision_id")
            deduplicated = action.metadata.get("deduplicated", False)
            if deduplicated:
                return None
            if isinstance(decision_id, str) and decision_id:
                return decision_id
        return None


class PushWorthinessNode(BaseNode):
    """推送价值判定节点。

    基于 LLM 判断是否值得推送：
    - PUSH: 保持原决策
    - SKIP: 降分并标记为 IGNORE（记录但不推送）
    """

    name = "push_worthiness"

    def __init__(
        self,
        tools: ToolRegistry | None = None,
        llm_service: Any = None,
    ):
        super().__init__(tools)
        self.llm_service = llm_service
        self._biz_logger = structlog.get_logger("business").bind(
            event="push_worthiness"
        )

    async def process(self, state: AgentState) -> AgentState:
        """执行推送价值判定。"""
        if state.draft.blocked:
            return state

        if state.draft.preliminary_bucket in (None, DecisionBucket.IGNORE):
            return state

        if not state.match or not state.goal or not state.item:
            logger.warning("PushWorthiness: Missing match/goal/item")
            return state

        if not self.llm_service:
            state.draft.fallback_reason = "no_llm_service"
            self._apply_fail_closed(state)
            return state

        result, fallback_reason = await self.llm_service.judge_push_worthiness(
            prompt=None,
            goal_description=state.goal.description,
            item_title=state.item.title,
            item_snippet=state.item.snippet or "",
            match_score=state.match.score,
            match_reasons=state.match.reasons,
            user_id=state.goal.user_id,
        )

        if result:
            state.draft.push_worthiness = result.model_dump()
            if result.label == "SKIP":
                from src.core.config import settings

                lowered = math.nextafter(settings.DIGEST_MIN_SCORE, 0.0)
                state.draft.adjusted_score = lowered
                state.draft.record_ignore = True
                state.draft.preliminary_bucket = DecisionBucket.IGNORE
                self._biz_logger.info(
                    "push_worthiness_skip",
                    goal_id=state.goal.goal_id,
                    item_id=state.item.item_id,
                    match_score=state.match.score,
                    adjusted_score=lowered,
                    reason=result.reason,
                    confidence=result.confidence,
                    evidence=result.evidence,
                    user_id=state.goal.user_id,
                )
                logger.info(
                    f"PushWorthiness: SKIP item {state.item.item_id}, "
                    f"adjusted_score={lowered:.4f}"
                )
            else:
                state.draft.adjusted_score = state.match.score
        else:
            state.draft.fallback_reason = fallback_reason or "llm_no_response"
            self._apply_fail_closed(state)

        return state

    @staticmethod
    def _apply_fail_closed(state: AgentState) -> None:
        """Fail closed when push-worthiness cannot be determined."""
        from src.core.config import settings

        lowered = math.nextafter(settings.DIGEST_MIN_SCORE, 0.0)
        state.draft.adjusted_score = lowered
        state.draft.record_ignore = True
        state.draft.preliminary_bucket = DecisionBucket.IGNORE


class EmitActionsNode(BaseNode):
    """发出动作节点。

    根据最终分桶创建 ActionProposal：
    - IMMEDIATE/BATCH/DIGEST: 创建 EMIT_DECISION
    - IGNORE/BLOCKED: 不创建动作
    """

    name = "emit_actions"

    async def process(self, state: AgentState) -> AgentState:
        """执行发出动作。"""
        # 如果被阻止，创建 IGNORE 记录但不推送
        if state.draft.blocked:
            logger.info(f"EmitActions: Blocked by {state.draft.block_reason}")
            # 可以选择记录被阻止的决策
            return state

        bucket = state.draft.preliminary_bucket

        if bucket == DecisionBucket.IGNORE and not state.draft.record_ignore:
            logger.debug("EmitActions: IGNORE, no action")
            return state

        if not state.goal or not state.item:
            logger.warning("EmitActions: Missing goal or item")
            return state

        # 构建 dedupe_key
        dedupe_key = self._build_dedupe_key(
            state.goal.goal_id,
            state.item.item_id,
            bucket.value,
        )

        # 构建 reason
        reason = self._build_reason(state)

        # 构建 evidence
        evidence = self._build_evidence(state)

        # 构建 score_trace
        score_trace = self._build_score_trace(state)

        # 创建动作提案
        action = ActionProposal(
            action_type="EMIT_DECISION",
            decision=bucket.value,
            goal_id=state.goal.goal_id,
            item_id=state.item.item_id,
            reason=reason,
            evidence=evidence,
            dedupe_key=dedupe_key,
            metadata={
                "match_score": state.match.score if state.match else 0,
                "adjusted_score": state.draft.adjusted_score,
                "llm_used": state.draft.llm_proposal is not None,
                "llm_confidence": state.draft.llm_confidence,
                "record_ignore": state.draft.record_ignore,
                "fallback_reason": state.draft.fallback_reason,
            },
        )

        state.actions.append(action)

        logger.info(
            f"EmitActions: Created {bucket.value} decision for "
            f"goal={state.goal.goal_id}, item={state.item.item_id}"
        )

        # 如果有 tools，执行实际的决策记录
        if self.tools:
            status = "SKIPPED" if bucket == DecisionBucket.IGNORE else None
            result = await self.tools.call(
                "emit_decision",
                goal_id=state.goal.goal_id,
                item_id=state.item.item_id,
                decision=bucket.value,
                reason_json={
                    "reason": reason,
                    "evidence": evidence,
                    "score_trace": score_trace,
                    "match_features": state.match.features if state.match else {},
                    "match_reasons": state.match.reasons if state.match else {},
                },
                dedupe_key=dedupe_key,
                run_id=state.run_id,
                status=status,
            )
            if result.success:
                action.metadata["decision_id"] = result.data.get("id")
                action.metadata["deduplicated"] = result.data.get("deduplicated", False)

        return state

    def _build_dedupe_key(self, goal_id: str, item_id: str, decision: str) -> str:
        """构建幂等键。"""
        raw = f"{goal_id}:{item_id}:{decision}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _build_reason(self, state: AgentState) -> str:
        """构建推送原因。"""
        parts = []

        if state.match and state.match.reasons:
            summary = state.match.reasons.get("summary", "")
            if summary:
                parts.append(summary)

        if state.draft.llm_proposal:
            llm_reason = state.draft.llm_proposal.get("reason", "")
            if llm_reason:
                parts.append(f"LLM: {llm_reason}")

        if state.draft.push_worthiness:
            worth_reason = state.draft.push_worthiness.get("reason", "")
            if worth_reason:
                parts.append(f"LLM推送价值: {worth_reason}")

        return "；".join(parts) if parts else "基础匹配"

    def _build_evidence(self, state: AgentState) -> list[dict[str, Any]]:
        """构建证据列表。"""
        evidence = []

        if state.match and state.match.reasons:
            match_evidence = state.match.reasons.get("evidence", [])
            evidence.extend(match_evidence)

        if state.draft.llm_proposal:
            llm_evidence = state.draft.llm_proposal.get("evidence", [])
            evidence.extend(llm_evidence)

        if state.draft.push_worthiness:
            worth_evidence = state.draft.push_worthiness.get("evidence", [])
            evidence.extend(worth_evidence)

        return evidence

    def _build_score_trace(self, state: AgentState) -> dict[str, Any]:
        """构建评分链路信息。"""
        thresholds = state.metadata.get("thresholds", {})
        boundary_fallback = state.metadata.get("fallback_reason")
        llm_data = {
            "boundary_judge": state.draft.llm_proposal,
            "boundary_fallback_reason": boundary_fallback,
            "push_worthiness": state.draft.push_worthiness,
            "push_worthiness_fallback_reason": state.draft.fallback_reason,
        }
        return {
            "match_score": state.match.score if state.match else 0,
            "adjusted_score": (
                state.draft.adjusted_score
                if state.draft.adjusted_score is not None
                else (state.match.score if state.match else 0)
            ),
            "bucket": state.draft.preliminary_bucket.value
            if state.draft.preliminary_bucket
            else None,
            "thresholds": thresholds,
            "llm": llm_data,
        }


# ============================================
# Node 管道
# ============================================


class NodePipeline:
    """Node 管道。

    按顺序执行多个 Node。
    """

    def __init__(self, nodes: list[BaseNode]):
        self.nodes = nodes

    async def run(self, state: AgentState) -> AgentState:
        """运行管道。"""
        for node in self.nodes:
            try:
                state = await node.process(state)
                logger.debug(f"Pipeline: {node.name} completed")
            except Exception as e:
                logger.exception(f"Pipeline: {node.name} failed: {e}")
                raise

        return state


def create_immediate_pipeline(
    tools: ToolRegistry | None = None,
    llm_service: Any = None,
    redis_client: Any = None,
    thresholds: ThresholdConfig | None = None,
) -> NodePipeline:
    """创建 Immediate 路径的 Node 管道。"""
    nodes = [
        LoadContextNode(tools),
        RuleGateNode(tools),
        BucketNode(tools, thresholds),
        BoundaryJudgeNode(tools, llm_service),
        PushWorthinessNode(tools, llm_service),
        EmitActionsNode(tools),
        CoalesceNode(tools, redis_client),
    ]
    return NodePipeline(nodes)
