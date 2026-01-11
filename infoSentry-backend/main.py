"""infoSentry Backend - 信息追踪 Agent 系统入口。"""

import sentry_sdk
from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.routing import APIRoute
from loguru import logger
from starlette.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.domain.exceptions import DomainException
from src.core.infrastructure.ai import check_ai_service_health
from src.core.infrastructure.database.session import init_db, check_db_health
from src.core.infrastructure.redis import redis_client
from src.core.infrastructure.logging import setup_logging
from src.core.interfaces.http.exceptions import (
    BizException,
    biz_exception_handler,
    domain_exception_handler,
    global_exception_handler,
)
from src.core.interfaces.http.routers import api_router


def custom_generate_unique_id(route: APIRoute) -> str:
    """Generate unique operation IDs for OpenAPI."""
    if route.tags:
        return f"{route.tags[0]}-{route.name}"
    return route.name


# Initialize Sentry if configured
if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(
        dsn=str(settings.SENTRY_DSN),
        enable_tracing=True,
        environment=settings.ENVIRONMENT,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application lifespan manager."""
    setup_logging()
    logger.info("Starting infoSentry backend...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

    # Initialize database
    logger.info("Initializing database connection...")
    await init_db()

    # TODO: Register event handlers
    # TODO: Start background tasks/workers

    yield

    logger.info("Shutting down infoSentry backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="信息追踪 Agent 系统 - 抓取、匹配、推送一体化解决方案",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    root_path=settings.ROOTPATH,
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

# Exception handlers
app.add_exception_handler(BizException, biz_exception_handler)
app.add_exception_handler(DomainException, domain_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# CORS middleware
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint.

    检查所有关键依赖的健康状态：
    - PostgreSQL 数据库连接
    - Redis 连接
    - pgvector 扩展
    - OpenAI API（如果启用 AI 功能）

    Returns:
        健康检查结果，包含整体状态和各组件状态
    """
    # 并行检查所有依赖
    db_health_result = await check_db_health()
    redis_health_result = await redis_client.health_check()

    # 检查 AI 服务（如果启用）
    ai_health_result = None
    if settings.LLM_ENABLED or settings.EMBEDDING_ENABLED:
        ai_health_result = await check_ai_service_health()

    # 确定整体状态
    all_ok = (
        db_health_result.status.value == "ok"
        and redis_health_result.status.value == "ok"
    )
    db_ok = db_health_result.status.value == "ok"

    # AI 服务检查（如果启用）
    ai_ok = True  # 默认正常
    if ai_health_result:
        ai_ok = ai_health_result.status.value in ["ok", "skipped"]

    # 整体状态判断：
    # - healthy: 所有依赖正常
    # - degraded: 数据库正常但其他服务异常（可降级运行）
    # - unhealthy: 数据库异常
    if all_ok and ai_ok:
        overall_status = "healthy"
    elif db_ok:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    components = {
        "database": db_health_result.to_dict(),
        "redis": redis_health_result.to_dict(),
    }

    # 如果启用了 AI 功能，添加 AI 服务健康状态
    if ai_health_result:
        components["ai_service"] = ai_health_result.to_dict()

    return {
        "status": overall_status,
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0",
        "components": components,
        "feature_flags": {
            "llm_enabled": settings.LLM_ENABLED,
            "embedding_enabled": settings.EMBEDDING_ENABLED,
            "immediate_enabled": settings.IMMEDIATE_ENABLED,
            "email_enabled": settings.EMAIL_ENABLED,
        },
    }


@app.get("/", tags=["root"])
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to infoSentry API",
        "docs": f"{settings.API_V1_STR}/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.SERVER_PORT,
        reload=settings.ENVIRONMENT == "local",
    )

