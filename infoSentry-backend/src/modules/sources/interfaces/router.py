"""Source API routes."""

from fastapi import APIRouter, Depends, Query, status

from src.core.application.security import get_current_user_id
from src.core.config import settings
from src.core.interfaces.http.response import ApiResponse, PaginatedResponse
from src.modules.sources.application.commands import (
    CreateSourceCommand,
    DeleteSourceCommand,
    DisableSourceCommand,
    EnableSourceCommand,
    SubscribeSourceCommand,
    UpdateSourceCommand,
)
from src.modules.sources.application.dependencies import (
    get_create_source_handler,
    get_delete_source_handler,
    get_disable_source_handler,
    get_enable_source_handler,
    get_source_query_service,
    get_subscribe_source_handler,
    get_update_source_handler,
)
from src.modules.sources.application.handlers import (
    CreateSourceHandler,
    DeleteSourceHandler,
    DisableSourceHandler,
    EnableSourceHandler,
    SubscribeSourceHandler,
    UpdateSourceHandler,
)
from src.modules.sources.application.models import PublicSourceData, SourceData
from src.modules.sources.application.services import SourceQueryService
from src.modules.sources.interfaces.schemas import (
    CreateSourceRequest,
    PublicSourceResponse,
    SourceResponse,
    SourceType,
    UpdateSourceRequest,
)

router = APIRouter(prefix="/sources", tags=["sources"])


def _to_source_response(source: SourceData) -> SourceResponse:
    return SourceResponse(
        id=source.id,
        type=SourceType(source.type.value),
        name=source.name,
        is_private=source.is_private,
        enabled=source.enabled,
        fetch_interval_sec=source.fetch_interval_sec,
        next_fetch_at=source.next_fetch_at,
        last_fetch_at=source.last_fetch_at,
        error_streak=source.error_streak,
        config=source.config,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _to_public_source_response(source: PublicSourceData) -> PublicSourceResponse:
    return PublicSourceResponse(
        id=source.id,
        type=SourceType(source.type.value),
        name=source.name,
        is_private=source.is_private,
        enabled=source.enabled,
        fetch_interval_sec=source.fetch_interval_sec,
        next_fetch_at=source.next_fetch_at,
        last_fetch_at=source.last_fetch_at,
        error_streak=source.error_streak,
        config=source.config,
        created_at=source.created_at,
        updated_at=source.updated_at,
        is_subscribed=source.is_subscribed,
    )


@router.get(
    "",
    response_model=PaginatedResponse[SourceResponse],
    summary="获取我的信息源列表",
    description="获取当前用户的信息源列表，支持按类型过滤",
)
async def list_sources(
    type: SourceType | None = Query(None, description="源类型过滤"),
    page: int = Query(settings.DEFAULT_PAGE, ge=1, description="页码"),
    page_size: int = Query(
        settings.SOURCES_PAGE_SIZE, ge=1, le=100, description="每页数量"
    ),
    user_id: str = Depends(get_current_user_id),
    service: SourceQueryService = Depends(get_source_query_service),
) -> PaginatedResponse[SourceResponse]:
    """List all sources."""
    result = await service.list_sources(
        user_id=user_id,
        source_type=type.value if type else None,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse.create(
        items=[_to_source_response(item) for item in result.items],
        total=result.total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/public",
    response_model=PaginatedResponse[PublicSourceResponse],
    summary="获取公共信息源列表",
    description="获取公共信息源列表，支持按类型过滤",
)
async def list_public_sources(
    type: SourceType | None = Query(None, description="源类型过滤"),
    page: int = Query(settings.DEFAULT_PAGE, ge=1, description="页码"),
    page_size: int = Query(
        settings.SOURCES_PAGE_SIZE, ge=1, le=100, description="每页数量"
    ),
    user_id: str = Depends(get_current_user_id),
    service: SourceQueryService = Depends(get_source_query_service),
) -> PaginatedResponse[PublicSourceResponse]:
    """List public sources."""
    result = await service.list_public_sources(
        user_id=user_id,
        source_type=type.value if type else None,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse.create(
        items=[_to_public_source_response(item) for item in result.items],
        total=result.total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=ApiResponse[SourceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建信息源",
    description="创建新的信息源",
)
async def create_source(
    request: CreateSourceRequest,
    user_id: str = Depends(get_current_user_id),
    handler: CreateSourceHandler = Depends(get_create_source_handler),
    query_service: SourceQueryService = Depends(get_source_query_service),
) -> ApiResponse[SourceResponse]:
    """Create a new source."""
    command = CreateSourceCommand(
        user_id=user_id,
        type=request.type,
        name=request.name,
        is_private=request.is_private,
        config=request.config,
        fetch_interval_sec=request.fetch_interval_sec,
    )
    source = await handler.handle(command)

    return ApiResponse.success(
        data=_to_source_response(
            await query_service.get_source(source_id=source.id, user_id=user_id)
        ),
        message="Source created successfully",
    )


@router.get(
    "/{source_id}",
    response_model=ApiResponse[SourceResponse],
    summary="获取信息源详情",
    description="根据ID获取信息源详情",
)
async def get_source(
    source_id: str,
    user_id: str = Depends(get_current_user_id),
    service: SourceQueryService = Depends(get_source_query_service),
) -> ApiResponse[SourceResponse]:
    """Get source by ID."""
    source = await service.get_source(source_id=source_id, user_id=user_id)
    return ApiResponse.success(data=_to_source_response(source))


@router.put(
    "/{source_id}",
    response_model=ApiResponse[SourceResponse],
    summary="更新信息源",
    description="更新信息源配置",
)
async def update_source(
    source_id: str,
    request: UpdateSourceRequest,
    user_id: str = Depends(get_current_user_id),
    handler: UpdateSourceHandler = Depends(get_update_source_handler),
    query_service: SourceQueryService = Depends(get_source_query_service),
) -> ApiResponse[SourceResponse]:
    """Update a source."""
    command = UpdateSourceCommand(
        source_id=source_id,
        user_id=user_id,
        name=request.name,
        config=request.config,
        fetch_interval_sec=request.fetch_interval_sec,
    )
    source = await handler.handle(command)

    return ApiResponse.success(
        data=_to_source_response(
            await query_service.get_source(source_id=source.id, user_id=user_id)
        ),
        message="Source updated successfully",
    )


@router.post(
    "/{source_id}/enable",
    response_model=ApiResponse[SourceResponse],
    summary="启用信息源",
    description="启用信息源",
)
async def enable_source(
    source_id: str,
    user_id: str = Depends(get_current_user_id),
    handler: EnableSourceHandler = Depends(get_enable_source_handler),
    query_service: SourceQueryService = Depends(get_source_query_service),
) -> ApiResponse[SourceResponse]:
    """Enable a source."""
    command = EnableSourceCommand(source_id=source_id, user_id=user_id)
    await handler.handle(command)

    return ApiResponse.success(
        data=_to_source_response(
            await query_service.get_source(source_id=source_id, user_id=user_id)
        ),
        message="Source enabled",
    )


@router.post(
    "/{source_id}/disable",
    response_model=ApiResponse[SourceResponse],
    summary="禁用信息源",
    description="禁用信息源",
)
async def disable_source(
    source_id: str,
    user_id: str = Depends(get_current_user_id),
    handler: DisableSourceHandler = Depends(get_disable_source_handler),
    query_service: SourceQueryService = Depends(get_source_query_service),
) -> ApiResponse[SourceResponse]:
    """Disable a source."""
    command = DisableSourceCommand(source_id=source_id, user_id=user_id)
    await handler.handle(command)

    return ApiResponse.success(
        data=_to_source_response(
            await query_service.get_source(source_id=source_id, user_id=user_id)
        ),
        message="Source disabled",
    )


@router.delete(
    "/{source_id}",
    response_model=ApiResponse[dict[str, bool]],
    summary="取消订阅信息源",
    description="取消订阅信息源（公共源不可删除）",
)
async def delete_source(
    source_id: str,
    user_id: str = Depends(get_current_user_id),
    handler: DeleteSourceHandler = Depends(get_delete_source_handler),
) -> ApiResponse[dict[str, bool]]:
    """Delete a source."""
    command = DeleteSourceCommand(source_id=source_id, user_id=user_id)
    success = await handler.handle(command)

    return ApiResponse.success(
        data={"deleted": success},
        message="Source unsubscribed successfully",
    )


@router.post(
    "/{source_id}/subscribe",
    response_model=ApiResponse[SourceResponse],
    summary="订阅公共信息源",
    description="订阅公共信息源",
)
async def subscribe_source(
    source_id: str,
    user_id: str = Depends(get_current_user_id),
    handler: SubscribeSourceHandler = Depends(get_subscribe_source_handler),
    query_service: SourceQueryService = Depends(get_source_query_service),
) -> ApiResponse[SourceResponse]:
    """Subscribe to a source."""
    command = SubscribeSourceCommand(source_id=source_id, user_id=user_id)
    await handler.handle(command)
    source = await query_service.get_source(source_id=source_id, user_id=user_id)
    return ApiResponse.success(
        data=_to_source_response(source),
        message="Source subscribed successfully",
    )
