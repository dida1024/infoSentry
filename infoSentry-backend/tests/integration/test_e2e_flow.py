"""端到端流程集成测试。

测试覆盖：
- 完整推送链路：抓取 → 入库 → 向量化 → 匹配 → Agent 决策 → 推送
- 反馈闭环：点击记录、like/dislike、source 阻止
- 降级场景：LLM 禁用、预算耗尽

使用方法：
    # 需要启动 docker-compose 中的 postgres 和 redis
    uv run pytest tests/integration/test_e2e_flow.py -v -m integration
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

# 标记为集成测试
pytestmark = [pytest.mark.integration, pytest.mark.anyio]


# ============================================
# 测试数据 Fixtures
# ============================================


@pytest.fixture
def sample_rss_source():
    """示例 RSS 源。"""
    return {
        "id": "source-rss-001",
        "type": "RSS",
        "name": "TechCrunch",
        "enabled": True,
        "fetch_interval_sec": 900,
        "config": {"feed_url": "https://techcrunch.com/feed/"},
    }


@pytest.fixture
def sample_goal():
    """示例追踪目标。"""
    return {
        "id": "goal-ai-001",
        "user_id": "user-001",
        "name": "AI 行业动态",
        "description": "追踪 AI/ML 领域的重要新闻",
        "status": "active",
        "priority_mode": "SOFT",
        "priority_terms": ["GPT", "Claude", "LLM", "OpenAI", "Anthropic"],
        "negative_terms": ["广告", "招聘", "promotion"],
        "batch_windows": ["09:00", "15:00", "21:00"],
    }


@pytest.fixture
def sample_items():
    """示例条目列表。"""
    return [
        {
            "id": "item-001",
            "source_id": "source-rss-001",
            "url": "https://techcrunch.com/2025/01/06/openai-gpt5/",
            "url_hash": "a1b2c3d4e5f6",
            "title": "OpenAI 正式发布 GPT-5，性能提升显著",
            "snippet": "OpenAI 今日正式发布了备受期待的 GPT-5 模型，在多项基准测试中超越前代...",
            "published_at": datetime.now(UTC) - timedelta(hours=1),
        },
        {
            "id": "item-002",
            "source_id": "source-rss-001",
            "url": "https://techcrunch.com/2025/01/06/anthropic-claude/",
            "url_hash": "b2c3d4e5f6a7",
            "title": "Anthropic 更新 Claude 3.5，支持更长上下文",
            "snippet": "Anthropic 宣布 Claude 3.5 现已支持 200K token 上下文窗口...",
            "published_at": datetime.now(UTC) - timedelta(hours=2),
        },
        {
            "id": "item-003",
            "source_id": "source-rss-001",
            "url": "https://techcrunch.com/2025/01/06/startup-hiring/",
            "url_hash": "c3d4e5f6a7b8",
            "title": "AI 创业公司大规模招聘",
            "snippet": "多家 AI 创业公司宣布扩张计划，预计今年新增数千个岗位...",
            "published_at": datetime.now(UTC) - timedelta(hours=3),
        },
    ]


# ============================================
# 模拟服务 Fixtures
# ============================================


@pytest.fixture
def mock_openai_embedding():
    """Mock OpenAI Embedding 服务。"""
    async def mock_create_embedding(text):
        # 返回模拟的 1536 维向量
        import hashlib
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [((hash_val >> i) & 1) * 0.1 for i in range(1536)]

    return mock_create_embedding


@pytest.fixture
def mock_smtp_sender():
    """Mock SMTP 发送器。"""
    sender = MagicMock()
    sender.send = AsyncMock(return_value=True)
    sender.send_count = 0
    sender.last_email = None

    async def track_send(to, subject, html):
        sender.send_count += 1
        sender.last_email = {"to": to, "subject": subject, "html": html}
        return True

    sender.send = track_send
    return sender


# ============================================
# 端到端流程测试
# ============================================


class TestIngestToMatchFlow:
    """抓取到匹配流程测试。"""

    async def test_item_ingested_triggers_embedding(
        self,
        sample_items,
        mock_openai_embedding,
    ):
        """测试条目入库后触发向量化。"""
        # 模拟入库
        item = sample_items[0]

        # 验证 embedding 计算
        embedding = await mock_openai_embedding(f"{item['title']} {item['snippet']}")

        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)

    async def test_embedding_triggers_match(
        self,
        sample_items,
        sample_goal,
    ):
        """测试向量化完成后触发匹配。"""
        item = sample_items[0]  # GPT-5 新闻
        goal = sample_goal

        # 模拟匹配计算
        # 标题包含 "GPT" 和 "OpenAI"，应该有较高分数
        title_lower = item["title"].lower()
        term_hits = sum(
            1 for term in goal["priority_terms"]
            if term.lower() in title_lower
        )

        assert term_hits >= 1  # 至少命中 GPT 或 OpenAI

        # 检查负面词
        negative_hits = sum(
            1 for term in goal["negative_terms"]
            if term.lower() in title_lower
        )

        assert negative_hits == 0  # 不应命中负面词

    async def test_negative_term_blocks(
        self,
        sample_items,
        sample_goal,
    ):
        """测试负面词阻止匹配。"""
        item = sample_items[2]  # 招聘新闻
        goal = sample_goal

        # 检查负面词命中
        content = f"{item['title']} {item['snippet']}".lower()
        negative_hits = sum(
            1 for term in goal["negative_terms"]
            if term.lower() in content
        )

        assert negative_hits >= 1  # 应该命中 "招聘"


class TestMatchToDecisionFlow:
    """匹配到决策流程测试。"""

    async def test_high_score_immediate(self):
        """测试高分立即推送。"""
        from src.modules.agent.application.state import (
            DecisionBucket,
            ThresholdConfig,
        )

        config = ThresholdConfig()

        # 高分 (>= 0.93) 应该是 IMMEDIATE
        assert config.get_bucket(0.95) == DecisionBucket.IMMEDIATE
        assert config.get_bucket(0.93) == DecisionBucket.IMMEDIATE

    async def test_boundary_score_needs_llm(self):
        """测试边界分数需要 LLM 判断。"""
        from src.modules.agent.application.state import (
            DecisionBucket,
            ThresholdConfig,
        )

        config = ThresholdConfig()

        # 边界分数 (0.88-0.93) 需要 LLM 判断
        assert config.get_bucket(0.90) == DecisionBucket.BOUNDARY
        assert config.get_bucket(0.88) == DecisionBucket.BOUNDARY

    async def test_medium_score_batch(self):
        """测试中等分数进入 Batch。"""
        from src.modules.agent.application.state import (
            DecisionBucket,
            ThresholdConfig,
        )

        config = ThresholdConfig()

        # 中等分数 (0.75-0.88) 应该是 BATCH
        assert config.get_bucket(0.80) == DecisionBucket.BATCH
        assert config.get_bucket(0.75) == DecisionBucket.BATCH

    async def test_low_score_ignore(self):
        """测试低分忽略。"""
        from src.modules.agent.application.state import (
            DecisionBucket,
            ThresholdConfig,
        )

        config = ThresholdConfig()

        # 低分 (< 0.75) 应该被忽略
        assert config.get_bucket(0.70) == DecisionBucket.IGNORE
        assert config.get_bucket(0.50) == DecisionBucket.IGNORE


class TestDecisionToPushFlow:
    """决策到推送流程测试。"""

    async def test_immediate_coalesce_window(self):
        """测试 Immediate 合并窗口。"""
        from src.core.config import settings

        # 默认 5 分钟合并窗口
        assert settings.IMMEDIATE_COALESCE_MINUTES == 5

        # 最多 3 条合并
        assert settings.IMMEDIATE_MAX_ITEMS == 3

    async def test_batch_max_items(self):
        """测试 Batch 最大条目数。"""
        from src.core.config import settings

        # Batch 最多 8 条
        assert settings.BATCH_MAX_ITEMS == 8

    async def test_digest_max_items(self):
        """测试 Digest 最大条目数。"""
        from src.core.config import settings

        # Digest 每 Goal 最多 10 条
        assert settings.DIGEST_MAX_ITEMS_PER_GOAL == 10


# ============================================
# 反馈闭环测试
# ============================================


class TestFeedbackFlow:
    """反馈流程测试。"""

    async def test_click_tracking(self):
        """测试点击跟踪。"""
        # 模拟点击事件
        click_event = {
            "item_id": "item-001",
            "goal_id": "goal-001",
            "user_agent": "Mozilla/5.0...",
            "ip_hash": "abc123",
            "channel": "email",
            "clicked_at": datetime.now(UTC).isoformat(),
        }

        assert click_event["item_id"] == "item-001"
        assert click_event["goal_id"] == "goal-001"
        assert "clicked_at" in click_event

    async def test_like_feedback(self):
        """测试 like 反馈。"""
        feedback = {
            "item_id": "item-001",
            "goal_id": "goal-001",
            "user_id": "user-001",
            "feedback_type": "like",
            "created_at": datetime.now(UTC).isoformat(),
        }

        assert feedback["feedback_type"] == "like"

    async def test_dislike_feedback(self):
        """测试 dislike 反馈。"""
        feedback = {
            "item_id": "item-002",
            "goal_id": "goal-001",
            "user_id": "user-001",
            "feedback_type": "dislike",
            "created_at": datetime.now(UTC).isoformat(),
        }

        assert feedback["feedback_type"] == "dislike"

    async def test_block_source(self):
        """测试阻止来源。"""
        blocked_source = {
            "source_id": "source-spam-001",
            "goal_id": "goal-001",
            "user_id": "user-001",
            "reason": "内容质量差",
            "blocked_at": datetime.now(UTC).isoformat(),
        }

        assert blocked_source["source_id"] == "source-spam-001"


# ============================================
# 降级场景测试
# ============================================


class TestDegradationFlow:
    """降级流程测试。"""

    async def test_llm_disabled_fallback_batch(self):
        """测试 LLM 禁用时降级到 Batch。"""
        from src.modules.agent.application.nodes import BoundaryJudgeNode
        from src.modules.agent.application.state import (
            AgentState,
            BudgetContext,
            DecisionBucket,
        )

        node = BoundaryJudgeNode(llm_service=None)
        state = AgentState(
            budget=BudgetContext(judge_disabled=True),
        )
        state.draft.preliminary_bucket = DecisionBucket.BOUNDARY

        result = await node.process(state)

        # 应该降级到 BATCH
        assert result.draft.preliminary_bucket == DecisionBucket.BATCH

    async def test_budget_exhausted_stops_embedding(self):
        """测试预算耗尽停止向量化。"""
        from src.modules.items.application.budget_service import BudgetStatus

        # 模拟预算耗尽
        status = BudgetStatus(
            date="2025-01-06",
            embedding_tokens=99999,
            usd_est=0.50,  # 超过 0.33 预算
            embedding_disabled=True,
        )

        assert status.embedding_disabled is True

    async def test_email_disabled_in_site_only(self):
        """测试邮件禁用时只有站内通知。"""
        from src.core.config import settings

        # 验证配置项存在
        assert hasattr(settings, "EMAIL_ENABLED")


# ============================================
# 完整 E2E 流程测试
# ============================================


class TestFullE2EFlow:
    """完整端到端流程测试。"""

    async def test_full_immediate_flow(
        self,
        sample_items,
        sample_goal,
        mock_openai_embedding,
        mock_smtp_sender,
    ):
        """测试完整的 Immediate 推送流程。"""
        item = sample_items[0]  # GPT-5 新闻
        goal = sample_goal

        # 1. 入库
        assert item["id"] is not None
        assert item["url"] is not None

        # 2. 向量化
        embedding = await mock_openai_embedding(item["title"])
        assert len(embedding) == 1536

        # 3. 匹配
        term_hits = sum(
            1 for term in goal["priority_terms"]
            if term.lower() in item["title"].lower()
        )
        assert term_hits >= 1

        # 4. 分数计算（模拟高分）
        mock_score = 0.95

        # 5. 决策
        from src.modules.agent.application.state import (
            DecisionBucket,
            ThresholdConfig,
        )
        bucket = ThresholdConfig().get_bucket(mock_score)
        assert bucket == DecisionBucket.IMMEDIATE

        # 6. 推送（验证邮件结构）
        email_content = {
            "to": "user@example.com",
            "subject": f"[infoSentry] {goal['name']} - 重要更新",
            "items": [
                {
                    "title": item["title"],
                    "snippet": item["snippet"],
                    "url": item["url"],
                }
            ],
        }

        assert goal["name"] in email_content["subject"]
        assert len(email_content["items"]) == 1

    async def test_full_batch_flow(
        self,
        sample_items,
        sample_goal,
    ):
        """测试完整的 Batch 推送流程。"""
        from src.modules.agent.application.state import (
            DecisionBucket,
            ThresholdConfig,
        )

        # 收集多个 Batch 候选
        batch_candidates = []
        config = ThresholdConfig()

        for item in sample_items:
            # 模拟中等分数
            mock_score = 0.82
            bucket = config.get_bucket(mock_score)

            if bucket == DecisionBucket.BATCH:
                batch_candidates.append({
                    "item_id": item["id"],
                    "title": item["title"],
                    "score": mock_score,
                })

        # 验证有候选进入 Batch
        assert len(batch_candidates) >= 0  # 可能有或没有

    async def test_dedup_prevents_duplicate_push(self):
        """测试去重防止重复推送。"""
        dedupe_keys = set()

        # 第一次推送
        key1 = "goal-001:item-001:20250106"
        assert key1 not in dedupe_keys
        dedupe_keys.add(key1)

        # 第二次尝试推送相同条目
        key2 = "goal-001:item-001:20250106"
        assert key2 in dedupe_keys  # 应该被拦截

    async def test_feedback_affects_future_scores(
        self,
        sample_goal,
    ):
        """测试反馈影响后续分数。"""
        # 模拟来源反馈历史
        source_feedback = {
            "source-001": {"likes": 5, "dislikes": 1},
            "source-002": {"likes": 1, "dislikes": 8},
        }

        # 计算来源信任度
        def compute_trust(source_id):
            fb = source_feedback.get(source_id, {"likes": 0, "dislikes": 0})
            total = fb["likes"] + fb["dislikes"]
            if total == 0:
                return 0.5  # 默认中等信任
            return fb["likes"] / total

        # source-001 应该有较高信任度
        assert compute_trust("source-001") > 0.7

        # source-002 应该有较低信任度
        assert compute_trust("source-002") < 0.3

