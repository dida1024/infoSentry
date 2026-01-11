"""Database session management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import settings
from src.core.infrastructure.health import DatabaseHealthResult, HealthStatus

async_engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=settings.ENVIRONMENT == "local",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session with automatic transaction management."""
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        async with session.begin():
            yield session


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """获取异步数据库会话（上下文管理器版本）。

    用于非 FastAPI 依赖注入场景（如 Celery 任务）。

    Usage:
        async with get_async_session() as session:
            # 使用 session
            await session.commit()
    """
    session = AsyncSession(async_engine, expire_on_commit=False)
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """Initialize database connection."""
    try:
        async with async_engine.begin() as conn:
            # 测试连接
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


async def check_db_health() -> DatabaseHealthResult:
    """检查数据库健康状态。

    执行基础连接测试和扩展检查：
    1. PostgreSQL 连接状态
    2. 数据库版本信息
    3. pgvector 扩展可用性

    Returns:
        DatabaseHealthResult: 健康检查结果
    """
    try:
        async with async_engine.connect() as conn:
            # 检查连接
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()

            # 检查 pgvector 扩展
            ext_result = await conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            has_pgvector = ext_result.scalar() is not None

            return DatabaseHealthResult(
                status=HealthStatus.OK,
                connected=True,
                version=version.split(",")[0] if version else "unknown",
                pgvector=has_pgvector,
            )
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return DatabaseHealthResult(
            status=HealthStatus.ERROR,
            connected=False,
            error=str(e),
        )
