"""Agent 单元测试。

测试覆盖：
- AgentState 数据结构
- 阈值分桶逻辑
- 规则守门逻辑
- Node 处理
- 可解释性
"""

import pytest
from pydantic import ValidationError

from src.core.config import settings
from src.modules.agent.application.llm_service import (
    BoundaryJudgeOutput,
    MockLLMJudgeService,
    PushWorthinessOutput,
)
from src.modules.agent.application.nodes import (
    BoundaryJudgeNode,
    BucketNode,
    EmitActionsNode,
    NodePipeline,
    PushWorthinessNode,
    RuleGateNode,
)
from src.modules.agent.application.state import (
    ActionProposal,
    AgentState,
    BlockReason,
    BudgetContext,
    DecisionBucket,
    GoalContext,
    ItemContext,
    MatchContext,
    ThresholdConfig,
)
from src.modules.agent.application.tools import (
    BaseTool,
    ToolRegistry,
    ToolResult,
)

# 使用 anyio 作为异步测试后端
pytestmark = pytest.mark.anyio


# ============================================
# ThresholdConfig 测试
# ============================================


class TestThresholdConfig:
    """ThresholdConfig 测试。"""

    def test_immediate_bucket(self):
        """测试 IMMEDIATE 分桶。"""
        config = ThresholdConfig()
        assert config.get_bucket(0.95) == DecisionBucket.IMMEDIATE
        assert config.get_bucket(0.93) == DecisionBucket.IMMEDIATE
        assert config.get_bucket(1.0) == DecisionBucket.IMMEDIATE

    def test_boundary_bucket(self):
        """测试 BOUNDARY 分桶。"""
        config = ThresholdConfig()
        assert config.get_bucket(0.92) == DecisionBucket.BOUNDARY
        assert config.get_bucket(0.90) == DecisionBucket.BOUNDARY
        assert config.get_bucket(0.88) == DecisionBucket.BOUNDARY

    def test_batch_bucket(self):
        """测试 BATCH 分桶。"""
        config = ThresholdConfig()
        assert config.get_bucket(0.87) == DecisionBucket.BATCH
        assert config.get_bucket(0.80) == DecisionBucket.BATCH
        assert config.get_bucket(0.75) == DecisionBucket.BATCH

    def test_ignore_bucket(self):
        """测试 IGNORE 分桶。"""
        config = ThresholdConfig()
        assert config.get_bucket(0.74) == DecisionBucket.IGNORE
        assert config.get_bucket(0.50) == DecisionBucket.IGNORE
        assert config.get_bucket(0.0) == DecisionBucket.IGNORE

    def test_custom_thresholds(self):
        """测试自定义阈值。"""
        config = ThresholdConfig(
            immediate_threshold=0.90,
            boundary_lower=0.80,
            batch_threshold=0.60,
        )
        assert config.get_bucket(0.90) == DecisionBucket.IMMEDIATE
        assert config.get_bucket(0.85) == DecisionBucket.BOUNDARY
        assert config.get_bucket(0.70) == DecisionBucket.BATCH
        assert config.get_bucket(0.50) == DecisionBucket.IGNORE


# ============================================
# AgentState 测试
# ============================================


class TestAgentState:
    """AgentState 测试。"""

    def test_create_default_state(self):
        """测试创建默认状态。"""
        state = AgentState()

        assert state.run_id is not None
        assert state.trigger == "MatchComputed"
        assert state.goal is None
        assert state.item is None
        assert state.actions == []

    def test_create_state_with_context(self):
        """测试创建带上下文的状态。"""
        goal = GoalContext(
            goal_id="goal-123",
            user_id="user-1",
            name="AI 动态",
            description="追踪 AI 领域新闻",
            priority_mode="SOFT",
            must_terms=["GPT", "OpenAI"],
            negative_terms=["广告"],
        )
        item = ItemContext(
            item_id="item-456",
            source_id="src-789",
            title="OpenAI 发布 GPT-5",
            url="https://example.com/news",
        )
        match = MatchContext(
            score=0.92,
            features={"cosine": 0.85, "term_hits": 2},
            reasons={"summary": "命中关键词 GPT"},
        )

        state = AgentState(goal=goal, item=item, match=match)

        assert state.goal.goal_id == "goal-123"
        assert state.item.item_id == "item-456"
        assert state.match.score == 0.92

    def test_to_input_snapshot(self):
        """测试生成输入快照。"""
        state = AgentState(
            goal=GoalContext(
                goal_id="goal-1",
                user_id="user-1",
                name="Test",
                description="Test",
                priority_mode="SOFT",
            ),
            item=ItemContext(
                item_id="item-1",
                source_id="src-1",
                title="Test",
                url="https://test.com",
            ),
        )

        snapshot = state.to_input_snapshot()

        assert "run_id" in snapshot
        assert "trigger" in snapshot
        assert snapshot["goal"]["goal_id"] == "goal-1"
        assert snapshot["item"]["item_id"] == "item-1"

    def test_to_output_snapshot(self):
        """测试生成输出快照。"""
        state = AgentState()
        state.actions.append(
            ActionProposal(
                action_type="EMIT_DECISION",
                decision="IMMEDIATE",
                goal_id="goal-1",
                item_id="item-1",
                reason="Test",
            )
        )

        snapshot = state.to_output_snapshot()

        assert "run_id" in snapshot
        assert len(snapshot["actions"]) == 1
        assert snapshot["actions"][0]["decision"] == "IMMEDIATE"


# ============================================
# RuleGateNode 测试
# ============================================


class TestRuleGateNode:
    """RuleGateNode 测试。"""

    @pytest.fixture
    def rule_gate(self):
        return RuleGateNode()

    @pytest.fixture
    def sample_state(self):
        return AgentState(
            goal=GoalContext(
                goal_id="goal-1",
                user_id="user-1",
                name="Test Goal",
                description="Test",
                priority_mode="SOFT",
                must_terms=["AI", "GPT"],
                negative_terms=["广告", "spam"],
                blocked_sources=["blocked-source-1"],
            ),
            item=ItemContext(
                item_id="item-1",
                source_id="src-1",
                title="OpenAI 发布 GPT-5",
                url="https://example.com",
                snippet="这是一条关于 AI 的新闻",
            ),
        )

    async def test_pass_normal(self, rule_gate, sample_state):
        """测试正常通过。"""
        result = await rule_gate.process(sample_state)

        assert not result.draft.blocked
        assert result.draft.block_reason is None

    async def test_block_by_source(self, rule_gate, sample_state):
        """测试被来源阻止。"""
        sample_state.item.source_id = "blocked-source-1"

        result = await rule_gate.process(sample_state)

        assert result.draft.blocked
        assert result.draft.block_reason == BlockReason.BLOCKED_SOURCE

    async def test_block_by_negative_term(self, rule_gate, sample_state):
        """测试被负面词阻止。"""
        sample_state.item.title = "这是一条广告"

        result = await rule_gate.process(sample_state)

        assert result.draft.blocked
        assert result.draft.block_reason == BlockReason.NEGATIVE_TERM

    async def test_block_by_strict_mode(self, rule_gate, sample_state):
        """测试 STRICT 模式阻止。"""
        sample_state.goal.priority_mode = "STRICT"
        sample_state.item.title = "今天天气很好"  # 不包含 must_terms
        sample_state.item.snippet = "这是一条普通新闻"  # 也不包含 must_terms

        result = await rule_gate.process(sample_state)

        assert result.draft.blocked
        assert result.draft.block_reason == BlockReason.STRICT_NO_HIT

    async def test_strict_mode_with_hit(self, rule_gate, sample_state):
        """测试 STRICT 模式命中。"""
        sample_state.goal.priority_mode = "STRICT"
        # title 已包含 GPT

        result = await rule_gate.process(sample_state)

        assert not result.draft.blocked


# ============================================
# BucketNode 测试
# ============================================


class TestBucketNode:
    """BucketNode 测试。"""

    @pytest.fixture
    def bucket_node(self):
        return BucketNode()

    async def test_immediate_bucket(self, bucket_node):
        """测试 IMMEDIATE 分桶。"""
        state = AgentState(
            match=MatchContext(score=0.95, features={}, reasons={}),
        )

        result = await bucket_node.process(state)

        assert result.draft.preliminary_bucket == DecisionBucket.IMMEDIATE

    async def test_boundary_bucket(self, bucket_node):
        """测试 BOUNDARY 分桶。"""
        state = AgentState(
            match=MatchContext(score=0.90, features={}, reasons={}),
        )

        result = await bucket_node.process(state)

        assert result.draft.preliminary_bucket == DecisionBucket.BOUNDARY

    async def test_batch_bucket(self, bucket_node):
        """测试 BATCH 分桶。"""
        state = AgentState(
            match=MatchContext(score=0.80, features={}, reasons={}),
        )

        result = await bucket_node.process(state)

        assert result.draft.preliminary_bucket == DecisionBucket.BATCH

    async def test_ignore_bucket(self, bucket_node):
        """测试 IGNORE 分桶。"""
        state = AgentState(
            match=MatchContext(score=0.50, features={}, reasons={}),
        )

        result = await bucket_node.process(state)

        assert result.draft.preliminary_bucket == DecisionBucket.IGNORE

    async def test_skip_if_blocked(self, bucket_node):
        """测试已阻止时跳过。"""
        state = AgentState(
            match=MatchContext(score=0.95, features={}, reasons={}),
        )
        state.draft.blocked = True

        result = await bucket_node.process(state)

        # 不应该设置 preliminary_bucket
        assert result.draft.preliminary_bucket is None


# ============================================
# Decision Flow 测试（不入库，仅模拟）
# ============================================


class TestDecisionFlowSimulation:
    """模拟匹配分数 -> 推送状态（无工具、无入库）。"""

    @pytest.mark.parametrize(
        ("score", "expected_decision", "expected_actions"),
        [
            (0.70, None, 0),  # IGNORE
            (0.75, "BATCH", 1),
            (0.87, "BATCH", 1),
            (0.88, "BATCH", 1),  # BOUNDARY -> no LLM fallback to BATCH
            (0.92, "BATCH", 1),  # BOUNDARY -> no LLM fallback to BATCH
            (0.93, "IMMEDIATE", 1),
            (1.00, "IMMEDIATE", 1),
        ],
    )
    async def test_score_to_decision_without_persist(
        self, score: float, expected_decision: str | None, expected_actions: int
    ) -> None:
        """验证 70%~100% 分数在无入库情况下的决策输出。"""
        state = AgentState(
            goal=GoalContext(
                goal_id="goal-1",
                user_id="user-1",
                name="Test Goal",
                description="Test",
                priority_mode="SOFT",
            ),
            item=ItemContext(
                item_id="item-1",
                source_id="src-1",
                title="Test title",
                url="https://example.com",
            ),
            match=MatchContext(
                score=score,
                features={},
                reasons={"summary": "测试匹配"},
            ),
        )

        pipeline = NodePipeline(
            [
                BucketNode(),
                BoundaryJudgeNode(llm_service=None),
                EmitActionsNode(),
            ]
        )

        result = await pipeline.run(state)

        assert len(result.actions) == expected_actions
        if expected_decision is None:
            assert result.actions == []
        else:
            assert result.actions[0].decision == expected_decision


# ============================================
# BoundaryJudgeNode 测试
# ============================================


class TestBoundaryJudgeNode:
    """BoundaryJudgeNode 测试。"""

    async def test_skip_if_not_boundary(self):
        """测试非 BOUNDARY 时跳过。"""
        node = BoundaryJudgeNode()
        state = AgentState()
        state.draft.preliminary_bucket = DecisionBucket.IMMEDIATE

        result = await node.process(state)

        assert result.draft.preliminary_bucket == DecisionBucket.IMMEDIATE
        assert result.draft.llm_proposal is None

    async def test_fallback_if_judge_disabled(self):
        """测试 judge 禁用时降级。"""
        node = BoundaryJudgeNode()
        state = AgentState(
            budget=BudgetContext(judge_disabled=True),
        )
        state.draft.preliminary_bucket = DecisionBucket.BOUNDARY

        result = await node.process(state)

        assert result.draft.preliminary_bucket == DecisionBucket.BATCH
        assert result.metadata.get("fallback_reason") == "judge_disabled"

    async def test_fallback_if_no_llm_service(self):
        """测试无 LLM 服务时降级。"""
        node = BoundaryJudgeNode(llm_service=None)
        state = AgentState()
        state.draft.preliminary_bucket = DecisionBucket.BOUNDARY

        result = await node.process(state)

        assert result.draft.preliminary_bucket == DecisionBucket.BATCH

    async def test_llm_call_success(self):
        """测试 LLM 调用成功。"""
        mock_llm = MockLLMJudgeService(default_label="IMMEDIATE")
        node = BoundaryJudgeNode(llm_service=mock_llm)

        state = AgentState(
            goal=GoalContext(
                goal_id="g1",
                user_id="u1",
                name="Test",
                description="Test",
                priority_mode="SOFT",
            ),
            item=ItemContext(
                item_id="i1",
                source_id="s1",
                title="Test",
                url="https://test.com",
            ),
            match=MatchContext(score=0.87, features={}, reasons={}),
        )
        state.draft.preliminary_bucket = DecisionBucket.BOUNDARY

        result = await node.process(state)

        assert result.draft.preliminary_bucket == DecisionBucket.IMMEDIATE
        assert result.draft.llm_proposal is not None


# ============================================
# PushWorthinessNode 测试
# ============================================


class TestPushWorthinessNode:
    """PushWorthinessNode 测试。"""

    async def test_skip_decision(self):
        """测试 LLM 判定 SKIP。"""

        class MockWorthinessService:
            async def judge_push_worthiness(self, **kwargs):
                return (
                    PushWorthinessOutput(
                        label="SKIP",
                        confidence=0.8,
                        uncertain=False,
                        reason="不相关",
                        evidence=[],
                    ),
                    None,
                )

        node = PushWorthinessNode(llm_service=MockWorthinessService())
        state = AgentState(
            goal=GoalContext(
                goal_id="g1",
                user_id="u1",
                name="Test",
                description="Test",
                priority_mode="SOFT",
            ),
            item=ItemContext(
                item_id="i1",
                source_id="s1",
                title="Test",
                url="https://test.com",
            ),
            match=MatchContext(score=0.85, features={}, reasons={}),
        )
        state.draft.preliminary_bucket = DecisionBucket.BATCH

        result = await node.process(state)

        assert result.draft.preliminary_bucket == DecisionBucket.IGNORE
        assert result.draft.record_ignore is True
        assert result.draft.adjusted_score < settings.DIGEST_MIN_SCORE
        assert result.draft.push_worthiness is not None

    async def test_fallback_when_no_llm(self):
        """测试无 LLM 服务时回退。"""
        node = PushWorthinessNode(llm_service=None)
        state = AgentState(
            goal=GoalContext(
                goal_id="g1",
                user_id="u1",
                name="Test",
                description="Test",
                priority_mode="SOFT",
            ),
            item=ItemContext(
                item_id="i1",
                source_id="s1",
                title="Test",
                url="https://test.com",
            ),
            match=MatchContext(score=0.85, features={}, reasons={}),
        )
        state.draft.preliminary_bucket = DecisionBucket.BATCH

        result = await node.process(state)

        assert result.draft.fallback_reason == "no_llm_service"
        assert result.draft.preliminary_bucket == DecisionBucket.BATCH


# ============================================
# EmitActionsNode 测试
# ============================================


class TestEmitActionsNode:
    """EmitActionsNode 测试。"""

    async def test_emit_immediate_action(self):
        """测试发出 IMMEDIATE 动作。"""
        node = EmitActionsNode()
        state = AgentState(
            goal=GoalContext(
                goal_id="goal-1",
                user_id="user-1",
                name="Test",
                description="Test",
                priority_mode="SOFT",
            ),
            item=ItemContext(
                item_id="item-1",
                source_id="src-1",
                title="Test",
                url="https://test.com",
            ),
            match=MatchContext(
                score=0.95,
                features={},
                reasons={"summary": "测试原因"},
            ),
        )
        state.draft.preliminary_bucket = DecisionBucket.IMMEDIATE

        result = await node.process(state)

        assert len(result.actions) == 1
        assert result.actions[0].decision == "IMMEDIATE"
        assert result.actions[0].goal_id == "goal-1"
        assert result.actions[0].item_id == "item-1"

    async def test_no_action_for_ignore(self):
        """测试 IGNORE 不发出动作。"""
        node = EmitActionsNode()
        state = AgentState(
            goal=GoalContext(
                goal_id="goal-1",
                user_id="user-1",
                name="Test",
                description="Test",
                priority_mode="SOFT",
            ),
            item=ItemContext(
                item_id="item-1",
                source_id="src-1",
                title="Test",
                url="https://test.com",
            ),
        )
        state.draft.preliminary_bucket = DecisionBucket.IGNORE

        result = await node.process(state)

        assert len(result.actions) == 0

    async def test_record_ignore_action(self):
        """测试 record_ignore 时生成 IGNORE 动作。"""
        node = EmitActionsNode()
        state = AgentState(
            goal=GoalContext(
                goal_id="goal-1",
                user_id="user-1",
                name="Test",
                description="Test",
                priority_mode="SOFT",
            ),
            item=ItemContext(
                item_id="item-1",
                source_id="src-1",
                title="Test",
                url="https://test.com",
            ),
            match=MatchContext(score=0.2, features={}, reasons={}),
        )
        state.draft.preliminary_bucket = DecisionBucket.IGNORE
        state.draft.record_ignore = True

        result = await node.process(state)

        assert len(result.actions) == 1
        assert result.actions[0].decision == "IGNORE"

    async def test_no_action_if_blocked(self):
        """测试阻止时不发出动作。"""
        node = EmitActionsNode()
        state = AgentState(
            goal=GoalContext(
                goal_id="goal-1",
                user_id="user-1",
                name="Test",
                description="Test",
                priority_mode="SOFT",
            ),
            item=ItemContext(
                item_id="item-1",
                source_id="src-1",
                title="Test",
                url="https://test.com",
            ),
        )
        state.draft.blocked = True
        state.draft.preliminary_bucket = DecisionBucket.IMMEDIATE

        result = await node.process(state)

        assert len(result.actions) == 0


# ============================================
# NodePipeline 测试
# ============================================


class TestNodePipeline:
    """NodePipeline 测试。"""

    async def test_pipeline_execution(self):
        """测试管道执行。"""
        pipeline = NodePipeline(
            [
                BucketNode(),
                EmitActionsNode(),
            ]
        )

        state = AgentState(
            goal=GoalContext(
                goal_id="goal-1",
                user_id="user-1",
                name="Test",
                description="Test",
                priority_mode="SOFT",
            ),
            item=ItemContext(
                item_id="item-1",
                source_id="src-1",
                title="Test",
                url="https://test.com",
            ),
            match=MatchContext(score=0.95, features={}, reasons={}),
        )

        result = await pipeline.run(state)

        assert result.draft.preliminary_bucket == DecisionBucket.IMMEDIATE
        assert len(result.actions) == 1


# ============================================
# ToolRegistry 测试
# ============================================


class TestToolRegistry:
    """ToolRegistry 测试。"""

    def test_register_and_get(self):
        """测试注册和获取工具。"""
        registry = ToolRegistry()

        class MockTool(BaseTool):
            name = "mock_tool"

            async def execute(self, **kwargs):
                return ToolResult(success=True, data="test")

        registry.register(MockTool())

        assert registry.get("mock_tool") is not None
        assert registry.get("nonexistent") is None

    def test_list_tools(self):
        """测试列出工具。"""
        registry = ToolRegistry()

        class Tool1(BaseTool):
            name = "tool1"

            async def execute(self, **kwargs):
                return ToolResult(success=True)

        class Tool2(BaseTool):
            name = "tool2"

            async def execute(self, **kwargs):
                return ToolResult(success=True)

        registry.register(Tool1())
        registry.register(Tool2())

        tools = registry.list_tools()
        assert "tool1" in tools
        assert "tool2" in tools

    async def test_call_tool(self):
        """测试调用工具。"""
        registry = ToolRegistry()
        registry.set_run_id("run-123")

        class MockTool(BaseTool):
            name = "mock_tool"

            async def execute(self, **kwargs):
                return ToolResult(success=True, data={"key": "value"})

        registry.register(MockTool())

        result = await registry.call("mock_tool", param1="test")

        assert result.success
        assert result.data == {"key": "value"}

    async def test_call_nonexistent_tool(self):
        """测试调用不存在的工具。"""
        registry = ToolRegistry()

        result = await registry.call("nonexistent")

        assert not result.success
        assert "not found" in result.error.lower()

    async def test_tool_call_recording(self):
        """测试工具调用记录。"""
        registry = ToolRegistry()
        registry.set_run_id("run-123")

        class MockTool(BaseTool):
            name = "mock_tool"

            async def execute(self, **kwargs):
                return ToolResult(success=True)

        registry.register(MockTool())
        await registry.call("mock_tool")

        records = registry.get_call_records()
        assert len(records) == 1
        assert records[0].tool_name == "mock_tool"
        assert records[0].run_id == "run-123"


# ============================================
# BoundaryJudgeOutput 测试
# ============================================


class TestBoundaryJudgeOutput:
    """BoundaryJudgeOutput 测试。"""

    def test_valid_output(self):
        """测试有效输出。"""
        output = BoundaryJudgeOutput(
            label="IMMEDIATE",
            confidence=0.85,
            uncertain=False,
            reason="测试理由",
            evidence=[{"type": "TERM_HIT", "value": "AI"}],
        )

        assert output.label == "IMMEDIATE"
        assert output.confidence == 0.85

    def test_invalid_label(self):
        """测试无效标签。"""
        with pytest.raises(ValidationError):
            BoundaryJudgeOutput(
                label="INVALID",
                confidence=0.85,
                reason="测试",
            )

    def test_invalid_confidence(self):
        """测试无效置信度。"""
        with pytest.raises(ValidationError):
            BoundaryJudgeOutput(
                label="IMMEDIATE",
                confidence=1.5,  # 超出范围
                reason="测试",
            )


# ============================================
# PushWorthinessOutput 测试
# ============================================


class TestPushWorthinessOutput:
    """PushWorthinessOutput 测试。"""

    def test_valid_output(self):
        """测试有效输出。"""
        output = PushWorthinessOutput(
            label="PUSH",
            confidence=0.6,
            uncertain=False,
            reason="相关",
            evidence=[],
        )

        assert output.label == "PUSH"
        assert output.confidence == 0.6

    def test_invalid_label(self):
        """测试无效标签。"""
        with pytest.raises(ValidationError):
            PushWorthinessOutput(
                label="INVALID",
                confidence=0.5,
                reason="测试",
            )


# ============================================
# ActionProposal 测试
# ============================================


class TestActionProposal:
    """ActionProposal 测试。"""

    def test_create_proposal(self):
        """测试创建提案。"""
        proposal = ActionProposal(
            action_type="EMIT_DECISION",
            decision="IMMEDIATE",
            goal_id="goal-1",
            item_id="item-1",
            reason="命中关键词",
            evidence=[{"type": "TERM_HIT", "value": "AI"}],
            dedupe_key="abc123",
        )

        assert proposal.action_type == "EMIT_DECISION"
        assert proposal.decision == "IMMEDIATE"
        assert len(proposal.evidence) == 1

    def test_proposal_to_dict(self):
        """测试提案序列化。"""
        proposal = ActionProposal(
            action_type="EMIT_DECISION",
            decision="BATCH",
            goal_id="goal-1",
            item_id="item-1",
            reason="测试",
        )

        data = proposal.model_dump()

        assert data["action_type"] == "EMIT_DECISION"
        assert data["decision"] == "BATCH"
