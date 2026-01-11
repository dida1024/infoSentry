"""Agent API routes."""

import base64
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.core.config import settings
from src.core.infrastructure.redis.client import get_redis_client
from src.core.infrastructure.security.jwt import get_current_user_id
from src.core.interfaces.http.response import ApiResponse, CursorPaginatedResponse
from src.modules.agent.domain.entities import AgentRunStatus
from src.modules.agent.infrastructure.dependencies import (
    get_agent_action_ledger_repository,
    get_agent_run_repository,
    get_agent_tool_call_repository,
    get_budget_daily_repository,
)
from src.modules.agent.infrastructure.repositories import (
    PostgreSQLAgentActionLedgerRepository,
    PostgreSQLAgentRunRepository,
    PostgreSQLAgentToolCallRepository,
    PostgreSQLBudgetDailyRepository,
)
from src.modules.agent.interfaces.schemas import (
    ActionLedgerResponse,
    AgentRunDetailResponse,
    AgentRunSummaryResponse,
    BudgetResponse,
    ToolCallResponse,
)

router = APIRouter(tags=["agent"])


def _decode_cursor(cursor: str | None) -> tuple[int, int]:
    """Decode cursor to (page, page_size)."""
    if not cursor:
        return 1, 20
    try:
        decoded = base64.b64decode(cursor).decode()
        page, page_size = decoded.split(":")
        return int(page), int(page_size)
    except Exception:
        return 1, 20


def _encode_cursor(page: int, page_size: int) -> str:
    """Encode (page, page_size) to cursor."""
    return base64.b64encode(f"{page}:{page_size}".encode()).decode()


class AgentRunListResponse(CursorPaginatedResponse[AgentRunSummaryResponse]):
    """Agent run list response with cursor pagination."""

    pass


@router.get(
    "/agent/runs",
    response_model=AgentRunListResponse,
    summary="获取Agent运行记录",
    description="获取Agent运行记录列表",
)
async def list_agent_runs(
    goal_id: str | None = Query(None, description="Goal ID过滤"),
    cursor: str | None = Query(None, description="分页游标"),
    run_status: str | None = Query(None, alias="status", description="状态过滤"),
    _: str = Depends(get_current_user_id),
    run_repo: PostgreSQLAgentRunRepository = Depends(get_agent_run_repository),
) -> AgentRunListResponse:
    """List agent runs."""
    page, page_size = _decode_cursor(cursor)

    # Parse status filter
    status_filter = None
    if run_status:
        try:
            status_filter = AgentRunStatus(run_status)
        except ValueError:
            pass

    # Get runs
    if goal_id:
        runs, total = await run_repo.list_by_goal(
            goal_id=goal_id,
            status=status_filter,
            page=page,
            page_size=page_size,
        )
    else:
        runs, total = await run_repo.list_recent(
            page=page,
            page_size=page_size,
        )

    # Build responses
    responses = []
    for run in runs:
        responses.append(
            AgentRunSummaryResponse(
                id=run.id,
                trigger=run.trigger,
                goal_id=run.goal_id,
                status=run.status,
                llm_used=run.llm_used,
                model_name=run.model_name,
                latency_ms=run.latency_ms,
                created_at=run.created_at,
            )
        )

    has_more = (page * page_size) < total
    next_cursor = _encode_cursor(page + 1, page_size) if has_more else None

    return AgentRunListResponse.create(
        items=responses,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get(
    "/agent/runs/{run_id}",
    response_model=ApiResponse[AgentRunDetailResponse],
    summary="获取Agent运行详情",
    description="获取单次Agent运行的详细信息（包含工具调用和动作账本）",
)
async def get_agent_run(
    run_id: str,
    _: str = Depends(get_current_user_id),
    run_repo: PostgreSQLAgentRunRepository = Depends(get_agent_run_repository),
    tool_call_repo: PostgreSQLAgentToolCallRepository = Depends(
        get_agent_tool_call_repository
    ),
    ledger_repo: PostgreSQLAgentActionLedgerRepository = Depends(
        get_agent_action_ledger_repository
    ),
) -> ApiResponse[AgentRunDetailResponse]:
    """Get agent run detail."""
    run = await run_repo.get_by_id(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Agent run not found"},
        )

    # Get tool calls
    tool_calls = await tool_call_repo.list_by_run(run_id)
    tool_call_responses = [
        ToolCallResponse(
            id=tc.id,
            tool_name=tc.tool_name,
            input=tc.input_json,
            output=tc.output_json,
            status=tc.status,
            latency_ms=tc.latency_ms,
        )
        for tc in tool_calls
    ]

    # Get action ledger
    ledger_entries = await ledger_repo.list_by_run(run_id)
    ledger_responses = [
        ActionLedgerResponse(
            id=entry.id,
            action_type=entry.action_type,
            payload=entry.payload_json,
            created_at=entry.created_at,
        )
        for entry in ledger_entries
    ]

    response = AgentRunDetailResponse(
        id=run.id,
        trigger=run.trigger,
        goal_id=run.goal_id,
        status=run.status,
        input_snapshot=run.input_snapshot_json,
        output_snapshot=run.output_snapshot_json,
        final_actions=run.final_actions_json,
        budget_snapshot=run.budget_snapshot_json,
        llm_used=run.llm_used,
        model_name=run.model_name,
        latency_ms=run.latency_ms,
        error_message=run.error_message,
        created_at=run.created_at,
        tool_calls=tool_call_responses,
        action_ledger=ledger_responses,
    )

    return ApiResponse.success(data=response)


@router.post(
    "/agent/runs/{run_id}/replay",
    response_model=ApiResponse[dict],
    summary="重放Agent运行",
    description="基于历史运行记录重放Agent决策流程",
)
async def replay_agent_run(
    run_id: str,
    _: str = Depends(get_current_user_id),
    run_repo: PostgreSQLAgentRunRepository = Depends(get_agent_run_repository),
) -> ApiResponse[dict]:
    """Replay an agent run based on its input snapshot."""
    run = await run_repo.get_by_id(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Agent run not found"},
        )

    # Return the replay information
    # In production, this would trigger an actual replay
    return ApiResponse.success(
        data={
            "original_run_id": run_id,
            "input_snapshot": run.input_snapshot_json,
            "original_output": run.output_snapshot_json,
            "message": "Replay endpoint available. Use input_snapshot to manually replay.",
        },
        message="Replay information retrieved",
    )


@router.get(
    "/admin/budget",
    response_model=ApiResponse[BudgetResponse],
    summary="获取预算状态",
    description="获取当前预算使用状态",
)
async def get_budget_status(
    _: str = Depends(get_current_user_id),
    budget_repo: PostgreSQLBudgetDailyRepository = Depends(get_budget_daily_repository),
) -> ApiResponse[BudgetResponse]:
    """Get budget status."""
    budget = await budget_repo.get_or_create_today()

    return ApiResponse.success(
        data=BudgetResponse(
            date=budget.date,
            embedding_tokens_est=budget.embedding_tokens_est,
            judge_tokens_est=budget.judge_tokens_est,
            usd_est=budget.usd_est,
            embedding_disabled=budget.embedding_disabled,
            judge_disabled=budget.judge_disabled,
            daily_limit=settings.DAILY_USD_BUDGET,
        )
    )


class ConfigUpdateRequest(ApiResponse):
    """Config update request."""

    LLM_ENABLED: bool | None = None
    EMBEDDING_ENABLED: bool | None = None
    IMMEDIATE_ENABLED: bool | None = None
    EMAIL_ENABLED: bool | None = None


class ConfigResponse(ApiResponse):
    """Config response with current feature flags."""

    LLM_ENABLED: bool
    EMBEDDING_ENABLED: bool
    IMMEDIATE_ENABLED: bool
    EMAIL_ENABLED: bool


@router.get(
    "/admin/config",
    response_model=ApiResponse[dict],
    summary="获取当前配置",
    description="获取当前 feature flags 配置",
)
async def get_config(
    _: str = Depends(get_current_user_id),
) -> ApiResponse[dict]:
    """Get current config."""
    return ApiResponse.success(
        data={
            "LLM_ENABLED": settings.LLM_ENABLED,
            "EMBEDDING_ENABLED": settings.EMBEDDING_ENABLED,
            "IMMEDIATE_ENABLED": settings.IMMEDIATE_ENABLED,
            "EMAIL_ENABLED": settings.EMAIL_ENABLED,
            "DAILY_USD_BUDGET": settings.DAILY_USD_BUDGET,
            "IMMEDIATE_THRESHOLD": settings.IMMEDIATE_THRESHOLD,
            "BATCH_THRESHOLD": settings.BATCH_THRESHOLD,
            "BOUNDARY_LOW": settings.BOUNDARY_LOW,
            "BOUNDARY_HIGH": settings.BOUNDARY_HIGH,
        }
    )


@router.post(
    "/admin/config",
    response_model=ApiResponse[dict],
    summary="热更新配置",
    description="热更新 feature flags 配置（存储在 Redis 中）",
)
async def update_config(
    config: dict,
    _: str = Depends(get_current_user_id),
) -> ApiResponse[dict]:
    """Update config in Redis for hot reload.

    Supported keys:
    - LLM_ENABLED: bool
    - EMBEDDING_ENABLED: bool
    - IMMEDIATE_ENABLED: bool
    - EMAIL_ENABLED: bool
    """
    allowed_keys = {
        "LLM_ENABLED",
        "EMBEDDING_ENABLED",
        "IMMEDIATE_ENABLED",
        "EMAIL_ENABLED",
    }

    updated = {}
    try:
        redis = get_redis_client()

        for key, value in config.items():
            if key in allowed_keys:
                # Store in Redis with config: prefix
                await redis.set(f"config:{key}", str(value).lower())
                updated[key] = value

        return ApiResponse.success(
            data={"updated": updated},
            message="Configuration updated successfully",
        )
    except Exception as e:
        return ApiResponse.error(
            message=f"Failed to update config: {str(e)}",
            code=500,
        )


@router.get(
    "/admin/health",
    response_model=ApiResponse[dict],
    summary="健康检查",
    description="检查系统各组件健康状态",
)
async def health_check(
    _: str = Depends(get_current_user_id),
    budget_repo: PostgreSQLBudgetDailyRepository = Depends(get_budget_daily_repository),
) -> ApiResponse[dict]:
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "components": {
            "database": "unknown",
            "redis": "unknown",
        },
    }

    # Check database
    try:
        await budget_repo.get_or_create_today()
        health_status["components"]["database"] = "healthy"
    except Exception as e:
        health_status["components"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    # Check Redis
    try:
        redis = get_redis_client()
        is_ok = await redis.ping()
        health_status["components"]["redis"] = "healthy" if is_ok else "unhealthy"
    except Exception as e:
        health_status["components"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    return ApiResponse.success(data=health_status)


@router.get(
    "/admin/monitoring",
    response_model=ApiResponse[dict],
    summary="获取监控状态",
    description="获取完整的监控状态（队列、LLM、SMTP、预算等）",
)
async def get_monitoring_status(
    _: str = Depends(get_current_user_id),
) -> ApiResponse[dict]:
    """Get full monitoring status."""
    from src.modules.agent.application.monitoring_service import MonitoringService

    try:
        redis = get_redis_client()
        monitoring = MonitoringService(redis)
        status = await monitoring.check_all()

        return ApiResponse.success(data=status.to_dict())

    except Exception as e:
        return ApiResponse.error(
            message=f"Failed to get monitoring status: {str(e)}",
            code=500,
        )


@router.get(
    "/admin/workers",
    response_model=ApiResponse[dict],
    summary="获取 Worker 心跳状态",
    description="获取各个 Worker 的心跳状态",
)
async def get_worker_status(
    _: str = Depends(get_current_user_id),
) -> ApiResponse[dict]:
    """Get worker heartbeat status."""
    from src.modules.agent.application.monitoring_service import MonitoringService

    try:
        redis = get_redis_client()
        monitoring = MonitoringService(redis)
        workers_result = await monitoring.get_worker_heartbeats()

        return ApiResponse.success(data={"workers": workers_result.to_dict()})

    except Exception as e:
        return ApiResponse.error(
            message=f"Failed to get worker status: {str(e)}",
            code=500,
        )


@router.post(
    "/admin/budget/reset",
    response_model=ApiResponse[dict],
    summary="重置每日预算",
    description="重置当日预算（仅用于紧急情况或测试）",
)
async def reset_budget(
    _: str = Depends(get_current_user_id),
) -> ApiResponse[dict]:
    """Reset daily budget."""
    from src.modules.items.application.budget_service import BudgetService

    try:
        redis = get_redis_client()
        budget_service = BudgetService(redis)
        await budget_service.reset_daily_budget()

        return ApiResponse.success(
            data={"reset": True},
            message="Daily budget has been reset",
        )

    except Exception as e:
        return ApiResponse.error(
            message=f"Failed to reset budget: {str(e)}",
            code=500,
        )


@router.post(
    "/admin/enable/{feature}",
    response_model=ApiResponse[dict],
    summary="启用功能",
    description="启用指定的功能（解除熔断）",
)
async def enable_feature(
    feature: str,
    _: str = Depends(get_current_user_id),
) -> ApiResponse[dict]:
    """Enable a feature (lift circuit breaker)."""
    allowed_features = {"llm", "embedding", "immediate", "email"}

    if feature.lower() not in allowed_features:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": f"Unknown feature: {feature}",
            },
        )

    try:
        redis = get_redis_client()
        config_key = f"config:{feature.upper()}_ENABLED"
        await redis.set(config_key, "true")

        return ApiResponse.success(
            data={"feature": feature, "enabled": True},
            message=f"Feature {feature} has been enabled",
        )

    except Exception as e:
        return ApiResponse.error(
            message=f"Failed to enable feature: {str(e)}",
            code=500,
        )


@router.post(
    "/admin/disable/{feature}",
    response_model=ApiResponse[dict],
    summary="禁用功能",
    description="禁用指定的功能（手动降级）",
)
async def disable_feature(
    feature: str,
    _: str = Depends(get_current_user_id),
) -> ApiResponse[dict]:
    """Disable a feature (manual circuit breaker)."""
    allowed_features = {"llm", "embedding", "immediate", "email"}

    if feature.lower() not in allowed_features:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": f"Unknown feature: {feature}",
            },
        )

    try:
        redis = get_redis_client()
        config_key = f"config:{feature.upper()}_ENABLED"
        await redis.set(config_key, "false")

        return ApiResponse.success(
            data={"feature": feature, "enabled": False},
            message=f"Feature {feature} has been disabled",
        )

    except Exception as e:
        return ApiResponse.error(
            message=f"Failed to disable feature: {str(e)}",
            code=500,
        )
