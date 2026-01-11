"""User API routes."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.core.config import settings
from src.core.infrastructure.security.jwt import get_current_user_id
from src.core.interfaces.http.response import ApiResponse
from src.modules.users.application.commands import (
    ConsumeMagicLinkCommand,
    RequestMagicLinkCommand,
    UpdateProfileCommand,
)
from src.modules.users.application.handlers import (
    ConsumeMagicLinkHandler,
    RequestMagicLinkHandler,
    UpdateProfileHandler,
)
from src.modules.users.domain.exceptions import UserNotFoundError
from src.modules.users.infrastructure.dependencies import (
    get_consume_magic_link_handler,
    get_request_magic_link_handler,
    get_update_profile_handler,
    get_user_budget_usage_service,
    get_user_repository,
)
from src.modules.users.infrastructure.repositories import PostgreSQLUserRepository
from src.modules.users.interfaces.schemas import (
    ConsumeTokenResponse,
    MagicLinkResponse,
    RequestMagicLinkRequest,
    SessionResponse,
    UpdateProfileRequest,
    UserResponse,
    UserBudgetUsageResponse,
    UserBudgetUsageDay,
)
from src.modules.users.application.budget_service import UserBudgetUsageService

router = APIRouter(tags=["auth"])


@router.post(
    "/auth/request_link",
    response_model=MagicLinkResponse,
    status_code=status.HTTP_200_OK,
    summary="请求 Magic Link",
    description="发送 Magic Link 到用户邮箱用于登录",
)
async def request_magic_link(
    request: RequestMagicLinkRequest,
    handler: RequestMagicLinkHandler = Depends(get_request_magic_link_handler),
) -> MagicLinkResponse:
    """Request magic link for login."""
    command = RequestMagicLinkCommand(email=request.email)
    await handler.handle(command)

    # TODO: 实际发送邮件的逻辑应该在事件处理器中
    # 这里暂时只返回成功消息

    return MagicLinkResponse()


@router.get(
    "/auth/consume",
    response_model=ConsumeTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="消费 Magic Link",
    description="使用 Magic Link Token 完成登录",
)
async def consume_magic_link(
    token: str = Query(..., description="Magic link token"),
    handler: ConsumeMagicLinkHandler = Depends(get_consume_magic_link_handler),
) -> ConsumeTokenResponse:
    """Consume magic link and complete login."""
    command = ConsumeMagicLinkCommand(token=token)
    user, access_token = await handler.handle(command)

    expires_at = datetime.now() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    return ConsumeTokenResponse(
        session=SessionResponse(
            user_id=user.id,
            email=user.email,
            access_token=access_token,
            expires_at=expires_at,
        )
    )


@router.get(
    "/users/me",
    response_model=ApiResponse[UserResponse],
    summary="获取当前用户信息",
    description="获取当前登录用户的详细信息",
)
async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    user_repository: PostgreSQLUserRepository = Depends(get_user_repository),
) -> ApiResponse[UserResponse]:
    """Get current user info."""
    user = await user_repository.get_by_id(user_id)
    if not user:
        raise UserNotFoundError(user_id=user_id)

    return ApiResponse.success(
        data=UserResponse(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            status=user.status.value,
            display_name=user.display_name,
            timezone=user.timezone,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
    )


@router.put(
    "/users/me",
    response_model=ApiResponse[UserResponse],
    summary="更新用户资料",
    description="更新当前用户的资料信息",
)
async def update_profile(
    request: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
    handler: UpdateProfileHandler = Depends(get_update_profile_handler),
) -> ApiResponse[UserResponse]:
    """Update current user profile."""
    command = UpdateProfileCommand(
        user_id=user_id,
        display_name=request.display_name,
        timezone=request.timezone,
    )
    user = await handler.handle(command)

    return ApiResponse.success(
        data=UserResponse(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            status=user.status.value,
            display_name=user.display_name,
            timezone=user.timezone,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
        message="Profile updated successfully",
    )


@router.get(
    "/users/me/budget",
    response_model=ApiResponse[UserBudgetUsageResponse],
    summary="获取用户 AI 预算使用情况",
    description="按日期范围查询当前用户的 AI 预算使用情况",
)
async def get_user_budget_usage(
    start_date: date = Query(..., description="起始日期（YYYY-MM-DD）"),
    end_date: date = Query(..., description="结束日期（YYYY-MM-DD）"),
    user_id: str = Depends(get_current_user_id),
    budget_service: UserBudgetUsageService = Depends(get_user_budget_usage_service),
) -> ApiResponse[UserBudgetUsageResponse]:
    """Get current user's AI budget usage."""
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "end_date must be greater than or equal to start_date",
            },
        )

    summary = await budget_service.get_usage_summary(
        user_id=user_id, start_date=start_date, end_date=end_date
    )
    days = [
        UserBudgetUsageDay(
            date=day.date,
            embedding_tokens_est=day.embedding_tokens_est,
            judge_tokens_est=day.judge_tokens_est,
            usd_est=day.usd_est,
            daily_limit=day.daily_limit,
            usage_percent=day.usage_percent,
        )
        for day in summary.days
    ]

    return ApiResponse.success(
        data=UserBudgetUsageResponse(
            user_id=summary.user_id,
            start_date=summary.start_date,
            end_date=summary.end_date,
            total_embedding_tokens_est=summary.total_embedding_tokens_est,
            total_judge_tokens_est=summary.total_judge_tokens_est,
            total_usd_est=summary.total_usd_est,
            daily_limit=summary.daily_limit,
            days=days,
        )
    )
