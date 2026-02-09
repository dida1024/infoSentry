"""infoSentry Backend - 信息追踪 Agent 系统入口。"""

from collections.abc import Callable
from typing import Any, cast

import sentry_sdk
from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.routing import APIRoute
from loguru import logger
from starlette.middleware.cors import CORSMiddleware

from src.core.application import dependencies as core_app_deps
from src.core.application import security as app_security
from src.core.config import settings
from src.core.domain.exceptions import DomainException
from src.core.infrastructure.ai import check_ai_service_health
from src.core.infrastructure.ai.prompting import dependencies as prompting_infra_deps
from src.core.infrastructure.database.session import check_db_health, init_db
from src.core.infrastructure.logging import setup_logging
from src.core.infrastructure.redis import get_redis_client, redis_client
from src.core.infrastructure.security import jwt as infra_jwt
from src.core.interfaces.http.exceptions import (
    BizException,
    biz_exception_handler,
    domain_exception_handler,
    global_exception_handler,
)
from src.core.interfaces.http.routers import api_router
from src.modules.agent.application import dependencies as agent_app_deps
from src.modules.agent.infrastructure import dependencies as agent_infra_deps
from src.modules.api_keys.application import dependencies as api_keys_app_deps
from src.modules.api_keys.infrastructure import dependencies as api_keys_infra_deps
from src.modules.goals.application import dependencies as goals_app_deps
from src.modules.goals.infrastructure import dependencies as goals_infra_deps
from src.modules.items.application import dependencies as items_app_deps
from src.modules.items.infrastructure import dependencies as items_infra_deps
from src.modules.push.application import dependencies as push_app_deps
from src.modules.push.infrastructure import dependencies as push_infra_deps
from src.modules.sources.application import dependencies as sources_app_deps
from src.modules.sources.infrastructure import dependencies as sources_infra_deps
from src.modules.users.application import dependencies as users_app_deps
from src.modules.users.infrastructure import dependencies as users_infra_deps


def custom_generate_unique_id(route: APIRoute) -> str:
    """Generate unique operation IDs for OpenAPI."""
    if route.tags:
        return f"{route.tags[0]}-{route.name}"
    return route.name


# OpenAPI security scheme definitions for API Key + JWT dual-mode auth
openapi_security_schemes = {
    "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT Bearer token (for web interface sessions)",
    },
    "ApiKeyAuth": {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "API Key for agent/external integrations (prefix: isk_)",
    },
}


def custom_openapi():
    """Customize OpenAPI schema to include both auth schemes."""
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["components"] = schema.get("components", {})
    schema["components"]["securitySchemes"] = openapi_security_schemes
    app.openapi_schema = schema
    return schema


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
    description=(
        "信息追踪 Agent 系统 - 抓取、匹配、推送一体化解决方案\n\n"
        "## 认证方式\n\n"
        "支持两种认证方式：\n"
        "- **JWT Bearer**: Web 界面登录后自动获取\n"
        "- **API Key**: 在 X-API-Key 请求头中传递（适合 Agent 集成）"
    ),
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    root_path=settings.ROOTPATH,
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)
app.openapi = cast(Callable[[], dict[str, Any]], custom_openapi)

# Dependency overrides (application -> infrastructure)
from src.core.infrastructure.security.unified_auth import (  # noqa: E402
    get_current_auth,
    get_current_user_id_from_jwt_only,
)

app.dependency_overrides[app_security.get_current_auth] = get_current_auth
app.dependency_overrides[app_security.get_current_user_id] = (
    get_current_user_id_from_jwt_only
)
app.dependency_overrides[app_security.get_current_jwt_user_id] = (
    get_current_user_id_from_jwt_only
)

# API Keys module
app.dependency_overrides[api_keys_app_deps.get_api_key_repository] = (
    api_keys_infra_deps.get_api_key_repository
)

app.dependency_overrides[core_app_deps.get_prompt_store] = (
    prompting_infra_deps.get_prompt_store
)

app.dependency_overrides[agent_app_deps.get_agent_run_repository] = (
    agent_infra_deps.get_agent_run_repository
)
app.dependency_overrides[agent_app_deps.get_agent_tool_call_repository] = (
    agent_infra_deps.get_agent_tool_call_repository
)
app.dependency_overrides[agent_app_deps.get_agent_action_ledger_repository] = (
    agent_infra_deps.get_agent_action_ledger_repository
)
app.dependency_overrides[agent_app_deps.get_budget_daily_repository] = (
    agent_infra_deps.get_budget_daily_repository
)
app.dependency_overrides[agent_app_deps.get_kv_client] = get_redis_client

app.dependency_overrides[goals_app_deps.get_goal_repository] = (
    goals_infra_deps.get_goal_repository
)
app.dependency_overrides[goals_app_deps.get_push_config_repository] = (
    goals_infra_deps.get_push_config_repository
)
app.dependency_overrides[goals_app_deps.get_term_repository] = (
    goals_infra_deps.get_term_repository
)

app.dependency_overrides[items_app_deps.get_item_repository] = (
    items_infra_deps.get_item_repository
)
app.dependency_overrides[items_app_deps.get_goal_item_match_repository] = (
    items_infra_deps.get_goal_item_match_repository
)

app.dependency_overrides[push_app_deps.get_push_decision_repository] = (
    push_infra_deps.get_push_decision_repository
)
app.dependency_overrides[push_app_deps.get_click_event_repository] = (
    push_infra_deps.get_click_event_repository
)
app.dependency_overrides[push_app_deps.get_item_feedback_repository] = (
    push_infra_deps.get_item_feedback_repository
)
app.dependency_overrides[push_app_deps.get_blocked_source_repository] = (
    push_infra_deps.get_blocked_source_repository
)
app.dependency_overrides[push_app_deps.get_item_repository] = (
    items_infra_deps.get_item_repository
)
app.dependency_overrides[push_app_deps.get_source_repository] = (
    sources_infra_deps.get_source_repository
)
app.dependency_overrides[push_app_deps.get_goal_repository] = (
    goals_infra_deps.get_goal_repository
)

app.dependency_overrides[sources_app_deps.get_source_repository] = (
    sources_infra_deps.get_source_repository
)
app.dependency_overrides[sources_app_deps.get_source_subscription_repository] = (
    sources_infra_deps.get_source_subscription_repository
)

app.dependency_overrides[users_app_deps.get_user_repository] = (
    users_infra_deps.get_user_repository
)
app.dependency_overrides[users_app_deps.get_magic_link_repository] = (
    users_infra_deps.get_magic_link_repository
)
app.dependency_overrides[users_app_deps.get_device_session_repository] = (
    users_infra_deps.get_device_session_repository
)
app.dependency_overrides[users_app_deps.get_user_budget_daily_repository] = (
    users_infra_deps.get_user_budget_daily_repository
)
app.dependency_overrides[users_app_deps.get_token_service] = infra_jwt.get_token_service
app.dependency_overrides[users_app_deps.get_magic_link_email_queue] = (
    users_infra_deps.get_magic_link_email_queue
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
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
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
