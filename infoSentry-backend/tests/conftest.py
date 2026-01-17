"""
pytest 配置和共享 fixtures。

测试分层：
- unit/: 单元测试（不依赖外部服务）
- integration/: 集成测试（需要 DB/Redis）
- e2e/: 端到端测试（完整流程）

使用方法：
    # 运行所有测试
    uv run pytest

    # 只运行单元测试
    uv run pytest tests/unit/

    # 只运行集成测试（需要 Docker）
    uv run pytest tests/integration/ -m integration

    # 运行带覆盖率
    uv run pytest --cov=src --cov-report=html
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from src.core.config import Settings

# ============================================
# 配置 Fixtures
# ============================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """创建事件循环（session 级别共享）。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """测试环境配置。"""
    return Settings(
        ENVIRONMENT="local",
        POSTGRES_SERVER="localhost",
        POSTGRES_PORT=5432,
        POSTGRES_USER="postgres",
        POSTGRES_PASSWORD="postgres",
        POSTGRES_DB="infosentry_test",
        REDIS_URL="redis://localhost:6379/1",  # 使用 DB 1 隔离测试
        SECRET_KEY="test-secret-key-for-testing-only",
        LLM_ENABLED=False,  # 测试时默认禁用 LLM
        EMAIL_ENABLED=False,  # 测试时默认禁用邮件
    )


# ============================================
# 数据库 Fixtures
# ============================================


@pytest.fixture(scope="session")
async def test_engine():
    """创建测试数据库引擎（session 级别）。

    注意：需要运行 docker-compose up -d postgres 才能使用。
    """
    engine = create_async_engine(
        "postgresql+psycopg://postgres:postgres@localhost:5432/infosentry_test",
        echo=False,
        pool_pre_ping=True,
    )

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """提供事务回滚的数据库会话。

    每个测试在独立事务中运行，测试结束后自动回滚。
    """
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        async with session.begin():
            yield session
            # 测试结束后回滚
            await session.rollback()


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Mock 数据库会话（用于纯单元测试）。"""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    return session


# ============================================
# Redis Fixtures
# ============================================


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """Mock Redis 客户端。"""
    from src.core.infrastructure.redis.client import RedisClient

    client = MagicMock(spec=RedisClient)
    client.ping = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.incr = AsyncMock(return_value=1)
    client.health_check = AsyncMock(return_value={"status": "ok", "connected": True})
    return client


@pytest.fixture
async def redis_client():
    """真实 Redis 客户端（集成测试用）。

    注意：需要运行 docker-compose up -d redis 才能使用。
    """
    from src.core.infrastructure.redis.client import RedisClient

    client = RedisClient(url="redis://localhost:6379/1")

    # 清理测试数据
    await client.client.flushdb()

    yield client

    # 清理
    await client.client.flushdb()
    await client.close()


# ============================================
# HTTP Client Fixtures
# ============================================


@pytest.fixture
async def async_client(
    test_settings, mock_db_session, mock_redis_client
) -> AsyncGenerator[AsyncClient, None]:
    """异步 HTTP 客户端（用于 API 测试）。"""
    _ = test_settings
    from main import app
    from src.core.infrastructure.database.session import get_db_session
    from src.core.infrastructure.redis import get_redis_client

    # 覆盖依赖
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[get_redis_client] = lambda: mock_redis_client

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    # 清理依赖覆盖
    app.dependency_overrides.clear()


# ============================================
# 领域对象 Fixtures
# ============================================


@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    """示例用户数据。"""
    return {
        "id": "user-123",
        "email": "test@example.com",
        "display_name": "Test User",
        "timezone": "Asia/Shanghai",
        "status": "active",
    }


@pytest.fixture
def sample_source_data() -> dict[str, Any]:
    """示例信息源数据。"""
    return {
        "id": "source-123",
        "type": "RSS",
        "name": "Test RSS Feed",
        "enabled": True,
        "fetch_interval_sec": 900,
        "config": {"feed_url": "https://example.com/feed.xml"},
    }


@pytest.fixture
def sample_goal_data() -> dict[str, Any]:
    """示例目标数据。"""
    return {
        "id": "goal-123",
        "user_id": "user-123",
        "name": "AI 行业动态",
        "description": "追踪 AI 领域的重要新闻",
        "status": "active",
        "priority_mode": "STRICT",
        "priority_terms": ["GPT", "Claude", "LLM"],
        "negative_terms": ["广告"],
    }


@pytest.fixture
def sample_item_data() -> dict[str, Any]:
    """示例内容项数据。"""
    return {
        "id": "item-123",
        "source_id": "source-123",
        "url": "https://example.com/news/123",
        "url_hash": "abc123hash",
        "title": "OpenAI 发布 GPT-5",
        "snippet": "OpenAI 今日正式发布了备受期待的 GPT-5...",
        "published_at": datetime.now(UTC),
        "embedding_status": "pending",
    }


@pytest.fixture
def sample_match_data() -> dict[str, Any]:
    """示例匹配数据。"""
    return {
        "goal_id": "goal-123",
        "item_id": "item-123",
        "match_score": 0.92,
        "features_json": {
            "cosine": 0.85,
            "term_hits": 2,
            "recency": 0.95,
            "source_trust": 0.90,
        },
        "reasons_json": {
            "summary": "命中核心关键词「GPT」",
            "evidence": [{"type": "TERM_HIT", "value": "GPT-5", "field": "title"}],
        },
    }


# ============================================
# Mock 服务 Fixtures
# ============================================


@pytest.fixture
def mock_openai_client() -> MagicMock:
    """Mock OpenAI 客户端。"""
    client = MagicMock()

    # Mock embedding
    client.embeddings.create = AsyncMock(
        return_value=MagicMock(data=[MagicMock(embedding=[0.1] * 1536)])
    )

    # Mock chat completion
    client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"label": "BATCH", "confidence": 0.85, "reason": "test"}'
                    )
                )
            ]
        )
    )

    return client


@pytest.fixture
def mock_smtp_client() -> MagicMock:
    """Mock SMTP 客户端。"""
    client = MagicMock()
    client.send = MagicMock(return_value=True)
    return client


# ============================================
# 时间控制 Fixtures
# ============================================


@pytest.fixture
def frozen_time():
    """固定时间（用于测试时间敏感逻辑）。

    使用示例：
        def test_something(frozen_time):
            with frozen_time("2025-01-06 09:00:00"):
                # 在固定时间下测试
    """
    from datetime import datetime
    from unittest.mock import patch

    class FrozenTime:
        def __call__(self, time_str: str):
            frozen = datetime.fromisoformat(time_str).replace(tzinfo=UTC)
            return patch("datetime.datetime.now", return_value=frozen)

    return FrozenTime()


# ============================================
# 辅助函数
# ============================================


def create_test_id(prefix: str = "test") -> str:
    """生成测试用 ID。"""
    import uuid

    return f"{prefix}-{uuid.uuid4().hex[:8]}"
