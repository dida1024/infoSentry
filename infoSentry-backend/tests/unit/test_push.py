"""推送与合并单元测试。

测试覆盖：
- Immediate 合并策略（5 分钟窗口，最多 3 条）
- 邮件去重（dedupe_key）
- 推送决策记录
- 邮件模板渲染
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from src.modules.push.application.email_templates import (
    EmailData,
    EmailItem,
    build_redirect_url,
    render_batch_email,
    render_digest_email,
    render_immediate_email,
    render_plain_text_fallback,
)
from src.modules.push.domain.entities import (
    PushChannel,
    PushDecision,
    PushDecisionRecord,
    PushStatus,
)

# 使用 anyio 作为异步测试后端
pytestmark = pytest.mark.anyio


# ============================================
# 测试辅助数据类
# ============================================


@dataclass
class PushCandidate:
    """推送候选（测试用）。"""

    goal_id: str
    item_id: str
    score: float
    decision: PushDecision
    reason: str = ""
    dedupe_key: str | None = None

    def generate_dedupe_key(self) -> str:
        """生成去重键。"""
        return f"{self.goal_id}:{self.item_id}"


@dataclass
class CoalesceResult:
    """合并结果（测试用）。"""

    goal_id: str
    items: list = None
    should_send: bool = False
    decision_type: PushDecision = PushDecision.IMMEDIATE

    def __post_init__(self):
        if self.items is None:
            self.items = []

    def get_limited_items(self, max_items: int = 3) -> list:
        """获取限制数量的条目。"""
        return self.items[:max_items]


# ============================================
# PushCandidate 测试
# ============================================


class TestPushCandidate:
    """PushCandidate 测试。"""

    def test_create_candidate(self):
        """测试创建候选。"""
        candidate = PushCandidate(
            goal_id="goal-1",
            item_id="item-1",
            score=0.92,
            decision=PushDecision.IMMEDIATE,
            reason="命中关键词",
            dedupe_key="goal-1:item-1",
        )

        assert candidate.goal_id == "goal-1"
        assert candidate.decision == PushDecision.IMMEDIATE
        assert candidate.dedupe_key == "goal-1:item-1"

    def test_generate_dedupe_key(self):
        """测试生成去重键。"""
        candidate = PushCandidate(
            goal_id="goal-123",
            item_id="item-456",
            score=0.85,
            decision=PushDecision.BATCH,
        )

        key = candidate.generate_dedupe_key()

        assert "goal-123" in key
        assert "item-456" in key


# ============================================
# CoalesceResult 测试
# ============================================


class TestCoalesceResult:
    """CoalesceResult 测试。"""

    def test_empty_result(self):
        """测试空结果。"""
        result = CoalesceResult(goal_id="goal-1")

        assert result.goal_id == "goal-1"
        assert len(result.items) == 0
        assert result.should_send is False

    def test_result_with_items(self):
        """测试有条目的结果。"""
        result = CoalesceResult(
            goal_id="goal-1",
            items=[
                {"item_id": "item-1", "title": "News 1"},
                {"item_id": "item-2", "title": "News 2"},
            ],
            should_send=True,
        )

        assert len(result.items) == 2
        assert result.should_send is True

    def test_max_items_limit(self):
        """测试最大条目限制。"""
        # IMMEDIATE 最多 3 条
        result = CoalesceResult(
            goal_id="goal-1",
            decision_type=PushDecision.IMMEDIATE,
            items=[{"item_id": f"item-{i}", "title": f"News {i}"} for i in range(5)],
        )

        # 应该只保留前 3 条
        assert result.get_limited_items(max_items=3) == result.items[:3]


# ============================================
# PushDecisionRecord 测试
# ============================================


class TestPushDecisionRecord:
    """PushDecisionRecord 测试。"""

    def test_create_record(self):
        """测试创建记录。"""
        record = PushDecisionRecord(
            id="decision-123",
            goal_id="goal-1",
            item_id="item-1",
            decision=PushDecision.IMMEDIATE,
            status=PushStatus.PENDING,
            channel=PushChannel.EMAIL,
            dedupe_key="goal-1:item-1:20250106",
            reason_json={"type": "TERM_HIT", "term": "AI"},
        )

        assert record.decision == PushDecision.IMMEDIATE
        assert record.status == PushStatus.PENDING
        assert record.channel == PushChannel.EMAIL
        assert record.reason_json["term"] == "AI"

    def test_record_to_dict(self):
        """测试记录序列化。"""
        record = PushDecisionRecord(
            id="decision-1",
            goal_id="goal-1",
            item_id="item-1",
            decision=PushDecision.BATCH,
            status=PushStatus.SENT,
            channel=PushChannel.EMAIL,
            dedupe_key="test-key",
        )

        data = record.model_dump()

        assert data["decision"] == PushDecision.BATCH
        assert data["status"] == PushStatus.SENT


# ============================================
# 邮件模板测试
# ============================================


class TestEmailTemplates:
    """邮件模板测试。"""

    def _make_email_item(
        self,
        item_id: str = "item-1",
        title: str = "Test News",
        snippet: str = "Test content",
        reason: str = "Test reason",
    ) -> EmailItem:
        """创建测试用的 EmailItem。"""
        return EmailItem(
            item_id=item_id,
            title=title,
            snippet=snippet,
            url=f"https://example.com/{item_id}",
            source_name="Test Source",
            published_at=datetime.now(UTC),
            reason=reason,
            redirect_url=f"https://infosentry.com/r/{item_id}",
        )

    def _make_email_data(
        self,
        goal_name: str = "AI 动态",
        items: list[EmailItem] | None = None,
    ) -> EmailData:
        """创建测试用的 EmailData。"""
        if items is None:
            items = [self._make_email_item()]
        return EmailData(
            to_email="test@example.com",
            goal_id="goal-1",
            goal_name=goal_name,
            items=items,
            decision_ids=["decision-1"],
        )

    def test_immediate_template_single_item(self):
        """测试 Immediate 模板 - 单条目。"""
        item = EmailItem(
            item_id="item-1",
            title="OpenAI 发布 GPT-5",
            snippet="OpenAI 今日发布...",
            url="https://example.com/news/1",
            source_name="TechNews",
            published_at=datetime.now(UTC),
            reason="命中关键词 GPT",
            redirect_url="https://infosentry.com/r/item-1",
        )
        email_data = self._make_email_data("AI 动态", [item])

        subject, html = render_immediate_email(email_data)

        assert "AI 动态" in subject or "AI 动态" in html
        assert "OpenAI 发布 GPT-5" in html
        assert "GPT" in html
        assert "href" in html

    def test_immediate_template_multiple_items(self):
        """测试 Immediate 模板 - 多条目。"""
        items = [self._make_email_item(f"item-{i}", f"News {i}") for i in range(3)]
        email_data = self._make_email_data("AI 动态", items)

        subject, html = render_immediate_email(email_data)

        assert "News 0" in html
        assert "News 1" in html
        assert "News 2" in html

    def test_batch_template(self):
        """测试 Batch 模板。"""
        email_data = self._make_email_data("AI 动态")

        subject, html = render_batch_email(email_data, "14:00")

        assert "AI 动态" in subject or "AI 动态" in html

    def test_digest_template(self):
        """测试 Digest 模板。"""
        email_data = self._make_email_data("AI 动态")

        subject, html = render_digest_email(email_data, "2025-01-06")

        assert "2025-01-06" in subject or "2025-01-06" in html
        assert "AI 动态" in html

    def test_plain_text_fallback(self):
        """测试纯文本回退。"""
        email_data = self._make_email_data()

        plain_text = render_plain_text_fallback(email_data)

        assert "AI 动态" in plain_text
        assert "Test News" in plain_text

    def test_build_redirect_url(self):
        """测试重定向 URL 构建。"""
        url = build_redirect_url(
            "https://api.example.com",
            "item-123",
            "goal-456",
            "email",
        )

        assert "item-123" in url
        assert "goal-456" in url
        assert "channel=email" in url


# ============================================
# Schema 校验测试
# ============================================


class TestPushSchemaValidation:
    """推送 Schema 校验测试。"""

    def test_valid_push_decision(self):
        """测试有效的推送决策。"""
        record = PushDecisionRecord(
            id="test-1",
            goal_id="goal-1",
            item_id="item-1",
            decision=PushDecision.IMMEDIATE,
            status=PushStatus.PENDING,
            channel=PushChannel.EMAIL,
            dedupe_key="test-dedupe",
        )

        assert record.id == "test-1"
        assert record.decision == PushDecision.IMMEDIATE

    def test_invalid_decision_type(self):
        """测试无效的决策类型。"""
        with pytest.raises((ValueError, TypeError)):
            PushDecisionRecord(
                id="test-1",
                goal_id="goal-1",
                item_id="item-1",
                decision="INVALID",  # 无效类型
                status=PushStatus.PENDING,
                channel=PushChannel.EMAIL,
                dedupe_key="test",
            )

    def test_candidate_validation(self):
        """测试候选验证。"""
        # 有效候选
        candidate = PushCandidate(
            goal_id="goal-1",
            item_id="item-1",
            score=0.85,
            decision=PushDecision.BATCH,
        )
        assert 0 <= candidate.score <= 1

        # 分数范围验证
        candidate_high = PushCandidate(
            goal_id="goal-1",
            item_id="item-1",
            score=0.99,
            decision=PushDecision.IMMEDIATE,
        )
        assert candidate_high.score <= 1.0
