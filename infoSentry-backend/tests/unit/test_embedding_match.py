"""向量化与匹配单元测试。

测试覆盖：
- 预算熔断逻辑
- 匹配分数计算
- 词条命中检测
- 时效性计算
- 可解释性原因生成
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.goals.domain.entities import (
    Goal,
    GoalPriorityTerm,
    GoalStatus,
    PriorityMode,
    TermType,
)
from src.modules.items.application.budget_service import BudgetService, BudgetStatus
from src.modules.items.application.match_service import (
    MatchFeatures,
    MatchReasons,
    MatchResult,
    MatchService,
)
from src.modules.items.domain.entities import EmbeddingStatus, Item

# 使用 anyio 作为异步测试后端
pytestmark = pytest.mark.anyio


# ============================================
# BudgetStatus 测试
# ============================================


class TestBudgetStatus:
    """BudgetStatus 测试。"""

    def test_to_dict(self):
        """测试序列化。"""
        status = BudgetStatus(
            date="2025-01-06",
            embedding_tokens=1000,
            judge_tokens=200,
            usd_est=0.05,
            embedding_disabled=False,
            judge_disabled=True,
        )

        data = status.to_dict()

        assert data["date"] == "2025-01-06"
        assert data["embedding_tokens"] == 1000
        assert data["judge_tokens"] == 200
        assert data["usd_est"] == 0.05
        assert data["embedding_disabled"] is False
        assert data["judge_disabled"] is True

    def test_from_dict(self):
        """测试反序列化。"""
        data = {
            "date": "2025-01-06",
            "embedding_tokens": 500,
            "judge_tokens": 100,
            "usd_est": 0.02,
            "embedding_disabled": True,
            "judge_disabled": False,
        }

        status = BudgetStatus.from_dict(data)

        assert status.date == "2025-01-06"
        assert status.embedding_tokens == 500
        assert status.embedding_disabled is True


class TestBudgetService:
    """BudgetService 测试。"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis 客户端。"""
        redis = MagicMock()
        redis.get_json = AsyncMock(return_value=None)
        redis.set_json = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def budget_service(self, mock_redis):
        """创建 BudgetService 实例。"""
        return BudgetService(redis_client=mock_redis)

    async def test_get_status_empty(self, budget_service, mock_redis):
        """测试获取空状态。"""
        mock_redis.get_json.return_value = None

        status = await budget_service.get_status()

        assert status.embedding_tokens == 0
        assert status.judge_tokens == 0
        assert status.embedding_disabled is False

    async def test_get_status_existing(self, budget_service, mock_redis):
        """测试获取已存在的状态。"""
        mock_redis.get_json.return_value = {
            "date": "2025-01-06",
            "embedding_tokens": 1000,
            "judge_tokens": 200,
            "usd_est": 0.05,
            "embedding_disabled": False,
            "judge_disabled": False,
        }

        status = await budget_service.get_status()

        assert status.embedding_tokens == 1000
        assert status.usd_est == 0.05

    async def test_check_embedding_budget_allowed(self, budget_service, mock_redis):
        """测试预算允许的情况。"""
        mock_redis.get_json.return_value = {
            "date": "2025-01-06",
            "embedding_tokens": 100,
            "usd_est": 0.01,
            "embedding_disabled": False,
            "judge_disabled": False,
        }

        with patch(
            "src.modules.items.application.budget_service.settings"
        ) as mock_settings:
            mock_settings.EMBEDDING_ENABLED = True
            mock_settings.DAILY_USD_BUDGET = 0.33
            mock_settings.EMBED_PER_DAY = 500

            allowed, reason = await budget_service.check_embedding_budget()

            assert allowed is True
            assert reason is None

    async def test_check_embedding_budget_exhausted(self, budget_service, mock_redis):
        """测试预算耗尽的情况。"""
        mock_redis.get_json.return_value = {
            "date": "2025-01-06",
            "embedding_tokens": 100,
            "usd_est": 0.35,  # 超过预算
            "embedding_disabled": False,
            "judge_disabled": False,
        }

        with patch(
            "src.modules.items.application.budget_service.settings"
        ) as mock_settings:
            mock_settings.EMBEDDING_ENABLED = True
            mock_settings.DAILY_USD_BUDGET = 0.33
            mock_settings.EMBED_PER_DAY = 500

            allowed, reason = await budget_service.check_embedding_budget()

            assert allowed is False
            assert "exhausted" in reason.lower()

    async def test_check_embedding_budget_disabled(self, budget_service, mock_redis):
        """测试全局禁用的情况。"""
        with patch(
            "src.modules.items.application.budget_service.settings"
        ) as mock_settings:
            mock_settings.EMBEDDING_ENABLED = False

            allowed, reason = await budget_service.check_embedding_budget()

            assert allowed is False
            assert "disabled" in reason.lower()

    async def test_record_embedding_usage(self, budget_service, mock_redis):
        """测试记录使用量。"""
        mock_redis.get_json.return_value = {
            "date": "2025-01-06",
            "embedding_tokens": 100,
            "judge_tokens": 0,
            "usd_est": 0.01,
            "embedding_disabled": False,
            "judge_disabled": False,
        }

        await budget_service.record_embedding_usage(500)

        # 验证 set_json 被调用
        mock_redis.set_json.assert_called()
        call_args = mock_redis.set_json.call_args
        saved_data = call_args[0][1]

        assert saved_data["embedding_tokens"] == 600  # 100 + 500


# ============================================
# MatchFeatures 测试
# ============================================


class TestMatchFeatures:
    """MatchFeatures 测试。"""

    def test_to_dict(self):
        """测试序列化。"""
        features = MatchFeatures(
            cosine_similarity=0.85,
            term_hits=2,
            term_hit_details=[
                {"term": "AI", "count": 3},
                {"term": "GPT", "count": 1},
            ],
            negative_hits=0,
            recency_score=0.95,
            source_trust=0.8,
        )

        data = features.to_dict()

        assert data["cosine_similarity"] == 0.85
        assert data["term_hits"] == 2
        assert len(data["term_hit_details"]) == 2
        assert data["recency_score"] == 0.95


# ============================================
# MatchReasons 测试
# ============================================


class TestMatchReasons:
    """MatchReasons 测试。"""

    def test_to_dict_normal(self):
        """测试正常匹配的序列化。"""
        reasons = MatchReasons(
            summary="命中关键词「AI」；语义相关",
            evidence=[
                {"type": "TERM_HIT", "term": "AI", "count": 2},
                {"type": "SEMANTIC_MATCH", "similarity": 0.75},
            ],
            is_blocked=False,
        )

        data = reasons.to_dict()

        assert "AI" in data["summary"]
        assert len(data["evidence"]) == 2
        assert data["is_blocked"] is False

    def test_to_dict_blocked(self):
        """测试被阻止匹配的序列化。"""
        reasons = MatchReasons(
            summary="命中负面词：广告",
            is_blocked=True,
            block_reason="命中负面词：广告",
        )

        data = reasons.to_dict()

        assert data["is_blocked"] is True
        assert "广告" in data["block_reason"]


# ============================================
# MatchService 测试
# ============================================


class TestMatchService:
    """MatchService 测试。"""

    @pytest.fixture
    def mock_goal_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_term_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_item_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_match_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def match_service(
        self,
        mock_goal_repo,
        mock_term_repo,
        mock_item_repo,
        mock_match_repo,
        mock_event_bus,
    ):
        return MatchService(
            goal_repository=mock_goal_repo,
            term_repository=mock_term_repo,
            item_repository=mock_item_repo,
            match_repository=mock_match_repo,
            event_bus=mock_event_bus,
        )

    @pytest.fixture
    def sample_item(self):
        """创建示例 Item。"""
        return Item(
            id="item-123",
            source_id="source-456",
            url="https://example.com/article",
            url_hash="abc123",
            title="OpenAI 发布 GPT-5",
            snippet="OpenAI 今日正式发布了备受期待的 GPT-5 模型...",
            published_at=datetime.now(UTC) - timedelta(hours=2),
            ingested_at=datetime.now(UTC),
            embedding_status=EmbeddingStatus.DONE,
            embedding=[0.1] * 1536,
        )

    @pytest.fixture
    def sample_goal(self):
        """创建示例 Goal。"""
        return Goal(
            id="goal-789",
            user_id="user-001",
            name="AI 行业动态",
            description="追踪 AI 领域的重要新闻",
            status=GoalStatus.ACTIVE,
            priority_mode=PriorityMode.SOFT,
        )

    def test_check_term_hits_single(self, match_service):
        """测试单个词条命中。"""
        text = "OpenAI 发布了最新的 GPT-5 模型"
        terms = [
            GoalPriorityTerm(
                id="term-1",
                goal_id="goal-1",
                term="GPT",
                term_type=TermType.MUST,
            ),
        ]

        hits, details = match_service._check_term_hits(text, terms)

        assert hits == 1
        assert len(details) == 1
        assert details[0]["term"] == "GPT"
        assert details[0]["count"] == 1

    def test_check_term_hits_multiple(self, match_service):
        """测试多个词条命中。"""
        text = "OpenAI 和 Claude 都是 AI 领域的领先者"
        terms = [
            GoalPriorityTerm(
                id="t1", goal_id="g1", term="OpenAI", term_type=TermType.MUST
            ),
            GoalPriorityTerm(
                id="t2", goal_id="g1", term="Claude", term_type=TermType.MUST
            ),
            GoalPriorityTerm(
                id="t3", goal_id="g1", term="Google", term_type=TermType.MUST
            ),
        ]

        hits, details = match_service._check_term_hits(text, terms)

        assert hits == 2  # OpenAI 和 Claude
        assert len(details) == 2

    def test_check_term_hits_case_insensitive(self, match_service):
        """测试大小写不敏感匹配。"""
        text = "openai 是一家 AI 公司"
        terms = [
            GoalPriorityTerm(
                id="t1", goal_id="g1", term="OpenAI", term_type=TermType.MUST
            ),
        ]

        hits, _ = match_service._check_term_hits(text, terms)

        assert hits == 1

    def test_check_term_hits_no_match(self, match_service):
        """测试无命中情况。"""
        text = "今天天气很好"
        terms = [
            GoalPriorityTerm(id="t1", goal_id="g1", term="AI", term_type=TermType.MUST),
        ]

        hits, details = match_service._check_term_hits(text, terms)

        assert hits == 0
        assert len(details) == 0

    def test_check_term_hits_chinese(self, match_service):
        """测试中文关键词匹配。"""
        text = "招聘后端开发工程师，要求熟悉 Python"
        terms = [
            GoalPriorityTerm(
                id="term-1",
                goal_id="goal-1",
                term="招聘",
                term_type=TermType.MUST,
            ),
            GoalPriorityTerm(
                id="term-2",
                goal_id="goal-1",
                term="后端",
                term_type=TermType.MUST,
            ),
        ]

        hits, details = match_service._check_term_hits(text, terms)

        assert hits == 2
        assert len(details) == 2
        assert details[0]["term"] == "招聘"
        assert details[0]["count"] == 1
        assert details[1]["term"] == "后端"
        assert details[1]["count"] == 1

    def test_check_term_hits_mixed_chinese_english(self, match_service):
        """测试中英文混合关键词匹配。"""
        text = "招聘 Python 后端开发"
        terms = [
            GoalPriorityTerm(
                id="t1", goal_id="g1", term="招聘", term_type=TermType.MUST
            ),
            GoalPriorityTerm(
                id="t2", goal_id="g1", term="Python", term_type=TermType.MUST
            ),
            GoalPriorityTerm(
                id="t3", goal_id="g1", term="后端", term_type=TermType.MUST
            ),
        ]

        hits, details = match_service._check_term_hits(text, terms)

        assert hits == 3
        assert len(details) == 3

    def test_compute_recency_score_fresh(self, match_service):
        """测试新鲜内容的时效性分数。"""
        item = Item(
            id="item-1",
            source_id="src-1",
            url="https://example.com",
            url_hash="hash1",
            title="Test",
            published_at=datetime.now(UTC) - timedelta(hours=2),
            ingested_at=datetime.now(UTC),
            embedding_status=EmbeddingStatus.PENDING,
        )

        score = match_service._compute_recency_score(item)

        assert score >= 0.8  # 2 小时内应该接近满分

    def test_compute_recency_score_old(self, match_service):
        """测试旧内容的时效性分数。"""
        item = Item(
            id="item-1",
            source_id="src-1",
            url="https://example.com",
            url_hash="hash1",
            title="Test",
            published_at=datetime.now(UTC) - timedelta(days=5),
            ingested_at=datetime.now(UTC),
            embedding_status=EmbeddingStatus.PENDING,
        )

        score = match_service._compute_recency_score(item)

        assert score < 0.5  # 5 天前的内容分数应该较低

    def test_compute_recency_score_very_old(self, match_service):
        """测试非常旧内容的时效性分数。"""
        item = Item(
            id="item-1",
            source_id="src-1",
            url="https://example.com",
            url_hash="hash1",
            title="Test",
            published_at=datetime.now(UTC) - timedelta(days=10),
            ingested_at=datetime.now(UTC),
            embedding_status=EmbeddingStatus.PENDING,
        )

        score = match_service._compute_recency_score(item)

        assert score == 0.0  # 10 天前的内容分数应该为 0

    def test_generate_reasons_with_term_hits(self, match_service, sample_goal):
        """测试有词条命中时的原因生成。"""
        item = MagicMock()
        item.title = "GPT-5 发布"

        features = MatchFeatures(
            cosine_similarity=0.7,
            term_hits=1,
            term_hit_details=[{"term": "GPT", "count": 1}],
            recency_score=0.9,
        )
        must_terms = [
            GoalPriorityTerm(
                id="t1", goal_id="g1", term="GPT", term_type=TermType.MUST
            ),
        ]

        reasons = match_service._generate_reasons(
            sample_goal, item, features, must_terms
        )

        assert not reasons.is_blocked
        assert "GPT" in reasons.summary
        assert any(e["type"] == "TERM_HIT" for e in reasons.evidence)

    def test_generate_reasons_with_negative_hit(self, match_service, sample_goal):
        """测试命中负面词时的原因生成。"""
        item = MagicMock()

        features = MatchFeatures(
            cosine_similarity=0.7,
            negative_hits=1,
            negative_hit_details=[{"term": "广告", "count": 1}],
        )
        must_terms = []

        reasons = match_service._generate_reasons(
            sample_goal, item, features, must_terms
        )

        assert reasons.is_blocked
        assert "广告" in reasons.block_reason

    def test_generate_reasons_strict_mode_no_hit(self, match_service):
        """测试 STRICT 模式下未命中的原因生成。"""
        goal = Goal(
            id="goal-1",
            user_id="user-1",
            name="Test Goal",
            description="Test",
            status=GoalStatus.ACTIVE,
            priority_mode=PriorityMode.STRICT,
        )
        item = MagicMock()

        features = MatchFeatures(
            cosine_similarity=0.7,
            term_hits=0,  # 未命中
        )
        must_terms = [
            GoalPriorityTerm(id="t1", goal_id="g1", term="AI", term_type=TermType.MUST),
        ]

        reasons = match_service._generate_reasons(goal, item, features, must_terms)

        assert reasons.is_blocked
        assert "STRICT" in reasons.block_reason

    def test_compute_final_score_normal(self, match_service, sample_goal):
        """测试正常情况下的分数计算。"""
        features = MatchFeatures(
            cosine_similarity=0.8,
            term_hits=2,
            recency_score=0.9,
            source_trust=0.8,
        )
        reasons = MatchReasons(is_blocked=False)

        score = match_service._compute_final_score(sample_goal, features, reasons)

        assert 0.6 < score < 1.0  # 综合分数应该较高

    def test_compute_final_score_blocked(self, match_service, sample_goal):
        """测试被阻止时的分数计算。"""
        features = MatchFeatures()
        reasons = MatchReasons(is_blocked=True)

        score = match_service._compute_final_score(sample_goal, features, reasons)

        assert score == 0.0

    def test_compute_final_score_high_semantic_no_terms(
        self, match_service, sample_goal
    ):
        """测试高语义相似度但无关键词命中的情况。"""
        features = MatchFeatures(
            cosine_similarity=0.85,
            term_hits=0,
            recency_score=1.0,
            source_trust=0.8,
        )
        reasons = MatchReasons(is_blocked=False)

        score = match_service._compute_final_score(sample_goal, features, reasons)

        # 高语义相似度应该得到较高分数（包含recency和source加分）
        assert 0.85 <= score <= 0.95

    def test_compute_final_score_medium_semantic_with_terms(
        self, match_service, sample_goal
    ):
        """测试中等语义相似度且有关键词命中的情况。"""
        features = MatchFeatures(
            cosine_similarity=0.70,
            term_hits=2,
            recency_score=1.0,
            source_trust=0.8,
        )
        reasons = MatchReasons(is_blocked=False)

        score = match_service._compute_final_score(sample_goal, features, reasons)

        # 中等语义+关键词应该得到高分数（包含recency和source加分）
        assert 0.85 <= score <= 1.0

    def test_compute_final_score_medium_semantic_no_terms(
        self, match_service, sample_goal
    ):
        """测试中等语义相似度但无关键词命中的情况。"""
        features = MatchFeatures(
            cosine_similarity=0.70,
            term_hits=0,
            recency_score=1.0,
            source_trust=0.8,
        )
        reasons = MatchReasons(is_blocked=False)

        score = match_service._compute_final_score(sample_goal, features, reasons)

        # 中等语义无关键词应该得到较低分数（包含recency和source加分）
        assert 0.50 <= score < 0.65

    async def test_match_item_to_goal(
        self,
        match_service,
        mock_term_repo,
        sample_item,
        sample_goal,
    ):
        """测试单个 Item 与 Goal 的匹配。"""
        # 设置 mock
        mock_term_repo.list_by_goal.return_value = [
            GoalPriorityTerm(
                id="t1", goal_id=sample_goal.id, term="GPT", term_type=TermType.MUST
            ),
        ]

        result = await match_service.match_item_to_goal(sample_item, sample_goal)

        assert result.goal_id == sample_goal.id
        assert result.item_id == sample_item.id
        assert result.score > 0
        assert "GPT" in result.reasons.summary


# ============================================
# MatchResult 测试
# ============================================


class TestMatchResult:
    """MatchResult 测试。"""

    def test_is_valid_normal(self):
        """测试正常匹配的有效性。"""
        result = MatchResult(
            goal_id="goal-1",
            item_id="item-1",
            score=0.85,
            features=MatchFeatures(),
            reasons=MatchReasons(is_blocked=False),
        )

        assert result.is_valid is True

    def test_is_valid_blocked(self):
        """测试被阻止匹配的有效性。"""
        result = MatchResult(
            goal_id="goal-1",
            item_id="item-1",
            score=0.0,
            features=MatchFeatures(),
            reasons=MatchReasons(is_blocked=True, block_reason="负面词命中"),
        )

        assert result.is_valid is False
