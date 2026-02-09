"""User API routes."""

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request, Response, status

from src.core.application.security import get_current_jwt_user_id
from src.core.config import settings
from src.core.interfaces.http.response import ApiResponse
from src.modules.users.application.budget_service import UserBudgetUsageService
from src.modules.users.application.commands import (
    ConsumeMagicLinkCommand,
    RefreshSessionCommand,
    RequestMagicLinkCommand,
    RevokeSessionCommand,
    UpdateProfileCommand,
)
from src.modules.users.application.dependencies import (
    get_consume_magic_link_handler,
    get_refresh_session_handler,
    get_request_magic_link_handler,
    get_revoke_session_handler,
    get_update_profile_handler,
    get_user_budget_usage_service,
    get_user_query_service,
)
from src.modules.users.application.handlers import (
    ConsumeMagicLinkHandler,
    RefreshSessionHandler,
    RequestMagicLinkHandler,
    RevokeSessionHandler,
    UpdateProfileHandler,
)
from src.modules.users.application.query_service import UserQueryService
from src.modules.users.domain.exceptions import RefreshTokenMissingError
from src.modules.users.interfaces.schemas import (
    ConsumeTokenResponse,
    LogoutResponse,
    MagicLinkResponse,
    RefreshSessionResponse,
    RequestMagicLinkRequest,
    SessionResponse,
    UpdateProfileRequest,
    UserBudgetUsageDay,
    UserBudgetUsageResponse,
    UserResponse,
)

router = APIRouter(tags=["auth"])


def _get_request_ip(request: Request) -> str | None:
    if settings.TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
    if not request.client:
        return None
    return request.client.host


def _get_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    normalized_expires = (
        expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
    )
    now = datetime.now(normalized_expires.tzinfo or UTC)
    max_age = max(0, int((normalized_expires - now).total_seconds()))
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=token,
        httponly=settings.REFRESH_COOKIE_HTTPONLY,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        path=settings.REFRESH_COOKIE_PATH,
        max_age=max_age,
        expires=normalized_expires,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        path=settings.REFRESH_COOKIE_PATH,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        secure=settings.REFRESH_COOKIE_SECURE,
    )


@router.post(
    "/auth/request_link",
    response_model=ApiResponse[MagicLinkResponse],
    status_code=status.HTTP_200_OK,
    summary="请求 Magic Link",
    description="发送 Magic Link 到用户邮箱用于登录",
)
async def request_magic_link(
    request: RequestMagicLinkRequest,
    handler: RequestMagicLinkHandler = Depends(get_request_magic_link_handler),
) -> ApiResponse[MagicLinkResponse]:
    """Request magic link for login."""
    command = RequestMagicLinkCommand(email=request.email)
    await handler.handle(command)

    response = MagicLinkResponse()
    return ApiResponse.success(data=response, message=response.message)


@router.get(
    "/auth/consume",
    response_model=ApiResponse[ConsumeTokenResponse],
    status_code=status.HTTP_200_OK,
    summary="消费 Magic Link",
    description="使用 Magic Link Token 完成登录",
)
async def consume_magic_link(
    request: Request,
    response: Response,
    token: str = Query(..., description="Magic link token"),
    handler: ConsumeMagicLinkHandler = Depends(get_consume_magic_link_handler),
) -> ApiResponse[ConsumeTokenResponse]:
    """Consume magic link and complete login."""
    client_ip = _get_request_ip(request)
    user_agent = _get_user_agent(request)
    command = ConsumeMagicLinkCommand(
        token=token,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    user, access_token, refresh_payload = await handler.handle(command)

    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    _set_refresh_cookie(response, refresh_payload.token, refresh_payload.expires_at)

    response_body = ConsumeTokenResponse(
        session=SessionResponse(
            user_id=user.id,
            email=user.email,
            access_token=access_token,
            expires_at=expires_at,
        )
    )
    return ApiResponse.success(data=response_body)


@router.post(
    "/auth/refresh",
    response_model=ApiResponse[RefreshSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="刷新登录会话",
    description="使用 refresh cookie 刷新访问令牌",
)
async def refresh_session(
    request: Request,
    response: Response,
    handler: RefreshSessionHandler = Depends(get_refresh_session_handler),
) -> ApiResponse[RefreshSessionResponse]:
    """Refresh login session."""
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise RefreshTokenMissingError()

    command = RefreshSessionCommand(
        refresh_token=refresh_token,
        ip_address=_get_request_ip(request),
        user_agent=_get_user_agent(request),
    )
    access_token, refresh_payload = await handler.handle(command)

    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    _set_refresh_cookie(response, refresh_payload.token, refresh_payload.expires_at)
    response_body = RefreshSessionResponse(
        access_token=access_token,
        expires_at=expires_at,
    )
    return ApiResponse.success(data=response_body)


@router.post(
    "/auth/logout",
    response_model=ApiResponse[LogoutResponse],
    status_code=status.HTTP_200_OK,
    summary="退出登录",
    description="撤销 refresh 会话并清除登录状态",
)
async def logout(
    request: Request,
    response: Response,
    handler: RevokeSessionHandler = Depends(get_revoke_session_handler),
) -> ApiResponse[LogoutResponse]:
    """Logout current session."""
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if refresh_token:
        command = RevokeSessionCommand(refresh_token=refresh_token)
        await handler.handle(command)

    _clear_refresh_cookie(response)
    response_body = LogoutResponse()
    return ApiResponse.success(data=response_body, message=response_body.message)


@router.get(
    "/users/me",
    response_model=ApiResponse[UserResponse],
    summary="获取当前用户信息",
    description="获取当前登录用户的详细信息",
)
async def get_current_user(
    user_id: str = Depends(get_current_jwt_user_id),
    service: UserQueryService = Depends(get_user_query_service),
) -> ApiResponse[UserResponse]:
    """Get current user info."""
    user = await service.get_current_user(user_id=user_id)
    return ApiResponse.success(data=UserResponse(**user.model_dump()))


@router.put(
    "/users/me",
    response_model=ApiResponse[UserResponse],
    summary="更新用户资料",
    description="更新当前用户的资料信息",
)
async def update_profile(
    request: UpdateProfileRequest,
    user_id: str = Depends(get_current_jwt_user_id),
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
    user_id: str = Depends(get_current_jwt_user_id),
    budget_service: UserBudgetUsageService = Depends(get_user_budget_usage_service),
) -> ApiResponse[UserBudgetUsageResponse]:
    """Get current user's AI budget usage."""
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
