"""OpenAI Embedding API 集成测试。

测试覆盖：
- OpenAI API 连接和认证
- Embedding 生成功能
- 预算服务集成
- EmbeddingService 端到端测试

使用方法：
    # 需要配置真实的 OPENAI_API_KEY 和启动 Redis
    uv run pytest tests/integration/test_embedding_api.py -v -m integration

注意：
    - 此测试会调用真实的 OpenAI API，产生少量费用（约 0.0001 USD）
    - 需要在 .env 中配置 EMBEDDING_ENABLED=true
    - 需要启动 Redis: docker-compose up -d redis
"""

from datetime import UTC, datetime

import pytest

from src.modules.items.domain.entities import EmbeddingStatus, Item

# 标记为集成测试
pytestmark = [pytest.mark.integration, pytest.mark.anyio]


# ============================================
# OpenAI API 连接测试
# ============================================


class TestOpenAIConnection:
    """测试 OpenAI API 基本连接。

    注意：这些测试需要真实的 OpenAI API Key。
    当 OPENAI_API_KEY 未配置时会自动跳过。
    """

    async def test_api_authentication(self, requires_openai_api):
        """测试 API 认证是否正确配置。"""
        from openai import AsyncOpenAI

        from src.core.config import settings

        # requires_openai_api fixture 已确保 API key 存在
        assert settings.OPENAI_API_BASE is not None, "OPENAI_API_BASE 未配置"
        assert settings.OPENAI_EMBED_MODEL is not None, "OPENAI_EMBED_MODEL 未配置"

        # 创建客户端
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE,
        )

        # 验证客户端可以创建
        assert client is not None

    async def test_embedding_generation(self, requires_openai_api):
        """测试基本的 Embedding 生成。"""
        from openai import AsyncOpenAI

        from src.core.config import settings

        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE,
        )

        try:
            # 调用 API
            test_text = "OpenAI 发布了最新的 GPT-5 模型，性能提升显著。"
            response = await client.embeddings.create(
                model=settings.OPENAI_EMBED_MODEL,
                input=test_text,
            )

            # 验证响应
            assert response.data is not None
            assert len(response.data) > 0

            embedding = response.data[0].embedding
            assert isinstance(embedding, list)
            assert len(embedding) == 1536  # text-embedding-3-small 维度
            assert all(isinstance(x, float) for x in embedding)

            # 验证 token 使用
            assert response.usage is not None
            assert response.usage.total_tokens > 0
        finally:
            await client.close()

    async def test_batch_embedding_generation(self, requires_openai_api):
        """测试批量 Embedding 生成。"""
        from openai import AsyncOpenAI

        from src.core.config import settings

        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE,
        )

        try:
            # 批量文本
            texts = [
                "OpenAI 发布 GPT-5",
                "Anthropic 更新 Claude 3.5",
                "Google 推出 Gemini Pro",
            ]

            response = await client.embeddings.create(
                model=settings.OPENAI_EMBED_MODEL,
                input=texts,
            )

            # 验证响应
            assert len(response.data) == len(texts)
            for item in response.data:
                assert len(item.embedding) == 1536
        finally:
            await client.close()


# ============================================
# 预算服务集成测试
# ============================================


class TestBudgetServiceIntegration:
    """测试预算服务与 Redis 集成。"""

    async def test_budget_check_with_redis(self, redis_client):
        """测试预算检查（使用真实 Redis）。"""
        from src.modules.items.application.budget_service import BudgetService

        budget_service = BudgetService(redis_client=redis_client)

        # 检查预算状态
        status = await budget_service.get_status()
        assert status.date is not None
        assert status.embedding_tokens >= 0
        assert status.usd_est >= 0

        # 检查是否允许嵌入
        allowed, reason = await budget_service.check_embedding_budget()
        assert isinstance(allowed, bool)

    async def test_record_embedding_usage(self, redis_client):
        """测试记录 Embedding 使用量。"""
        from src.modules.items.application.budget_service import BudgetService

        budget_service = BudgetService(redis_client=redis_client)

        # 记录前的状态
        status_before = await budget_service.get_status()
        tokens_before = status_before.embedding_tokens

        # 记录使用
        await budget_service.record_embedding_usage(100)

        # 验证记录成功
        status_after = await budget_service.get_status()
        assert status_after.embedding_tokens == tokens_before + 100
        assert status_after.usd_est > status_before.usd_est


# ============================================
# EmbeddingService 集成测试
# ============================================


class TestEmbeddingServiceIntegration:
    """测试 EmbeddingService 端到端流程。

    注意：这些测试需要真实的 OpenAI API Key 和 Redis。
    当 OPENAI_API_KEY 未配置时会自动跳过。
    """

    @pytest.fixture
    async def embedding_service(self, redis_client, requires_openai_api):
        """创建 EmbeddingService 实例。

        requires_openai_api fixture 确保 API key 已配置。
        """
        from unittest.mock import AsyncMock

        from src.modules.items.application.budget_service import BudgetService
        from src.modules.items.application.embedding_service import EmbeddingService

        # Mock item repository
        mock_repo = AsyncMock()
        mock_repo.update = AsyncMock()

        budget_service = BudgetService(redis_client=redis_client)

        service = EmbeddingService(
            item_repository=mock_repo,
            budget_service=budget_service,
        )

        yield service

        # 清理：关闭 OpenAI 客户端
        if service._client:
            await service._client.close()

    async def test_embed_single_item(self, embedding_service):
        """测试嵌入单个 Item。"""
        from src.core.config import settings

        # 创建测试 Item
        test_item = Item(
            id="test-item-001",
            source_id="test-source",
            url="https://example.com/test",
            url_hash="test-hash",
            title="OpenAI 发布 GPT-5",
            snippet="OpenAI 今日正式发布了备受期待的 GPT-5 模型，在多项基准测试中超越前代...",
            published_at=datetime.now(UTC),
            ingested_at=datetime.now(UTC),
            embedding_status=EmbeddingStatus.PENDING,
        )

        # 执行嵌入
        result = await embedding_service.embed_item(test_item)

        # 验证结果
        assert result.success is True
        assert result.item_id == test_item.id
        assert result.embedding is not None
        assert len(result.embedding) == 1536
        assert result.tokens_used > 0

        # 验证 Item 状态更新
        assert test_item.embedding_status == EmbeddingStatus.DONE
        assert test_item.embedding is not None
        assert test_item.embedding_model == settings.OPENAI_EMBED_MODEL

    async def test_embed_item_with_long_text(self, embedding_service):
        """测试嵌入长文本 Item。"""
        # 创建包含长文本的 Item
        long_snippet = "测试内容 " * 1000  # 创建长文本
        test_item = Item(
            id="test-item-002",
            source_id="test-source",
            url="https://example.com/test2",
            url_hash="test-hash-2",
            title="长文本测试",
            snippet=long_snippet,
            published_at=datetime.now(UTC),
            ingested_at=datetime.now(UTC),
            embedding_status=EmbeddingStatus.PENDING,
        )

        # 执行嵌入
        result = await embedding_service.embed_item(test_item)

        # 验证结果（应该截断文本但正常处理）
        assert result.success is True
        assert result.embedding is not None

    async def test_embed_item_without_text(self, embedding_service):
        """测试嵌入无文本的 Item。"""
        # 创建无文本的 Item
        test_item = Item(
            id="test-item-003",
            source_id="test-source",
            url="https://example.com/test3",
            url_hash="test-hash-3",
            title="",  # 空标题
            snippet="",  # 空摘要
            published_at=datetime.now(UTC),
            ingested_at=datetime.now(UTC),
            embedding_status=EmbeddingStatus.PENDING,
        )

        # 执行嵌入
        result = await embedding_service.embed_item(test_item)

        # 验证结果（应该失败）
        assert result.success is False
        assert result.error is not None
        assert "No text to embed" in result.error


# ============================================
# 配置验证测试
# ============================================


class TestEmbeddingConfiguration:
    """测试 Embedding 相关配置。"""

    def test_embedding_enabled_flag(self):
        """测试 EMBEDDING_ENABLED 配置。"""
        from src.core.config import settings

        # 验证配置项存在
        assert hasattr(settings, "EMBEDDING_ENABLED")
        assert isinstance(settings.EMBEDDING_ENABLED, bool)

    def test_openai_config_complete(self, requires_openai_api):
        """测试 OpenAI 配置完整性。"""
        from src.core.config import settings

        # 验证必需配置项
        assert hasattr(settings, "OPENAI_API_KEY")
        assert hasattr(settings, "OPENAI_API_BASE")
        assert hasattr(settings, "OPENAI_EMBED_MODEL")

        # requires_openai_api fixture 已确保 API key 存在
        assert settings.OPENAI_API_KEY is not None
        assert len(settings.OPENAI_API_KEY) > 0

    def test_budget_config_complete(self):
        """测试预算配置完整性。"""
        from src.core.config import settings

        # 验证预算配置项
        assert hasattr(settings, "DAILY_USD_BUDGET")
        assert hasattr(settings, "EMBED_PER_DAY")
        assert hasattr(settings, "EMBED_PER_MIN")

        # 验证配置值合理
        assert settings.DAILY_USD_BUDGET > 0
        assert settings.EMBED_PER_DAY > 0
        assert settings.EMBED_PER_MIN > 0
