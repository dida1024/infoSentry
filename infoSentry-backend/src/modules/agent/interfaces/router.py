"""Agent API routes."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.core.application.security import get_current_user_id
from src.core.interfaces.http.response import ApiResponse, CursorPaginatedResponse
from src.modules.agent.application.dependencies import (
    get_agent_admin_service,
    get_agent_run_query_service,
)
from src.modules.agent.application.services import (
    AgentAdminService,
    AgentRunQueryService,
)
from src.modules.agent.interfaces.schemas import (
    AgentRunDetailResponse,
    AgentRunSummaryResponse,
    BudgetResponse,
)

router = APIRouter(tags=["agent"])
logger = structlog.get_logger(__name__)


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
    service: AgentRunQueryService = Depends(get_agent_run_query_service),
) -> AgentRunListResponse:
    """List agent runs."""
    result = await service.list_runs(goal_id, cursor, run_status)

    responses = [AgentRunSummaryResponse(**item.model_dump()) for item in result.items]

    return AgentRunListResponse.create(
        items=responses,
        next_cursor=result.next_cursor,
        has_more=result.has_more,
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
    service: AgentRunQueryService = Depends(get_agent_run_query_service),
) -> ApiResponse[AgentRunDetailResponse]:
    """Get agent run detail."""
    detail = await service.get_run_detail(run_id)
    response = AgentRunDetailResponse(**detail.model_dump())
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
    service: AgentRunQueryService = Depends(get_agent_run_query_service),
) -> ApiResponse[dict]:
    """Replay an agent run based on its input snapshot."""
    replay_info = await service.get_replay_info(run_id)
    return ApiResponse.success(
        data=replay_info,
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
    service: AgentAdminService = Depends(get_agent_admin_service),
) -> ApiResponse[BudgetResponse]:
    """Get budget status."""
    budget = await service.get_budget_status()
    return ApiResponse.success(data=BudgetResponse(**budget.model_dump()))


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
    service: AgentAdminService = Depends(get_agent_admin_service),
) -> ApiResponse[dict]:
    """Get current config."""
    config = await service.get_config()
    return ApiResponse.success(data=config)


@router.post(
    "/admin/config",
    response_model=ApiResponse[dict],
    summary="热更新配置",
    description="热更新 feature flags 配置（存储在 Redis 中）",
)
async def update_config(
    config: dict,
    _: str = Depends(get_current_user_id),
    service: AgentAdminService = Depends(get_agent_admin_service),
) -> ApiResponse[dict]:
    """Update config in Redis for hot reload.

    Supported keys:
    - LLM_ENABLED: bool
    - EMBEDDING_ENABLED: bool
    - IMMEDIATE_ENABLED: bool
    - EMAIL_ENABLED: bool
    """
    try:
        updated = await service.update_config(config)
        return ApiResponse.success(
            data=updated,
            message="Configuration updated successfully",
        )
    except Exception as e:
        logger.exception("Failed to update config", error=str(e))
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
    service: AgentAdminService = Depends(get_agent_admin_service),
) -> ApiResponse[dict]:
    """Health check endpoint."""
    try:
        health_status = await service.health_check()
        return ApiResponse.success(data=health_status)
    except Exception as e:
        logger.exception("Failed to get health status", error=str(e))
        return ApiResponse.error(
            message=f"Failed to get health status: {str(e)}",
            code=500,
        )


@router.get(
    "/admin/monitoring",
    response_model=ApiResponse[dict],
    summary="获取监控状态",
    description="获取完整的监控状态（队列、LLM、SMTP、预算等）",
)
async def get_monitoring_status(
    _: str = Depends(get_current_user_id),
    service: AgentAdminService = Depends(get_agent_admin_service),
) -> ApiResponse[dict]:
    """Get full monitoring status."""

    try:
        status = await service.get_monitoring_status()
        return ApiResponse.success(data=status)

    except Exception as e:
        logger.exception("Failed to get monitoring status", error=str(e))
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
    service: AgentAdminService = Depends(get_agent_admin_service),
) -> ApiResponse[dict]:
    """Get worker heartbeat status."""

    try:
        workers_result = await service.get_worker_status()
        return ApiResponse.success(data=workers_result)

    except Exception as e:
        logger.exception("Failed to get worker status", error=str(e))
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
    service: AgentAdminService = Depends(get_agent_admin_service),
) -> ApiResponse[dict]:
    """Reset daily budget."""
    try:
        result = await service.reset_budget()
        return ApiResponse.success(
            data=result,
            message="Daily budget has been reset",
        )

    except Exception as e:
        logger.exception("Failed to reset budget", error=str(e))
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
    service: AgentAdminService = Depends(get_agent_admin_service),
) -> ApiResponse[dict]:
    """Enable a feature (lift circuit breaker)."""
    try:
        result = await service.enable_feature(feature)
        return ApiResponse.success(
            data=result,
            message=f"Feature {feature} has been enabled",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": f"Unknown feature: {feature}",
            },
        )
    except Exception as e:
        logger.exception("Failed to enable feature", error=str(e), feature=feature)
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
    service: AgentAdminService = Depends(get_agent_admin_service),
) -> ApiResponse[dict]:
    """Disable a feature (manual circuit breaker)."""
    try:
        result = await service.disable_feature(feature)
        return ApiResponse.success(
            data=result,
            message=f"Feature {feature} has been disabled",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": f"Unknown feature: {feature}",
            },
        )
    except Exception as e:
        logger.exception("Failed to disable feature", error=str(e), feature=feature)
        return ApiResponse.error(
            message=f"Failed to disable feature: {str(e)}",
            code=500,
        )
