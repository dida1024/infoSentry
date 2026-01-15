"""Goal API routes."""

from fastapi import APIRouter, Depends, Query, status

from src.core.application.security import get_current_user_id
from src.core.config import settings
from src.core.infrastructure.logging import get_business_logger
from src.core.interfaces.http.exceptions import BizException
from src.core.interfaces.http.response import ApiResponse, PaginatedResponse
from src.modules.goals.application.commands import (
    CreateGoalCommand,
    DeleteGoalCommand,
    PauseGoalCommand,
    ResumeGoalCommand,
    UpdateGoalCommand,
)
from src.modules.goals.application.dependencies import (
    get_create_goal_handler,
    get_delete_goal_handler,
    get_goal_draft_service,
    get_goal_match_query_service,
    get_goal_query_service,
    get_keyword_suggestion_service,
    get_pause_goal_handler,
    get_resume_goal_handler,
    get_update_goal_handler,
)
from src.modules.goals.application.goal_draft_service import (
    GoalDraftGenerationError,
    GoalDraftNotAvailableError,
    GoalDraftService,
)
from src.modules.goals.application.handlers import (
    CreateGoalHandler,
    DeleteGoalHandler,
    PauseGoalHandler,
    ResumeGoalHandler,
    UpdateGoalHandler,
)
from src.modules.goals.application.keyword_service import KeywordSuggestionService
from src.modules.goals.application.models import GoalData
from src.modules.goals.application.services import (
    GoalMatchQueryService,
    GoalQueryService,
)
from src.modules.goals.interfaces.schemas import (
    CreateGoalRequest,
    GenerateGoalDraftRequest,
    GenerateGoalDraftResponse,
    GoalItemMatchResponse,
    GoalResponse,
    GoalStatus,
    GoalStatusResponse,
    ItemResponse,
    PriorityMode,
    SuggestKeywordsRequest,
    SuggestKeywordsResponse,
    UpdateGoalRequest,
)

router = APIRouter(prefix="/goals", tags=["goals"])


def _to_goal_response(goal: GoalData) -> GoalResponse:
    return GoalResponse(
        id=goal.id,
        name=goal.name,
        description=goal.description,
        priority_mode=PriorityMode(goal.priority_mode.value),
        status=GoalStatus(goal.status.value),
        priority_terms=goal.priority_terms,
        negative_terms=goal.negative_terms,
        batch_windows=goal.batch_windows,
        digest_send_time=goal.digest_send_time,
        stats=goal.stats,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


@router.get(
    "",
    response_model=PaginatedResponse[GoalResponse],
    summary="获取Goal列表",
    description="获取当前用户的所有Goal",
)
async def list_goals(
    status: GoalStatus | None = Query(None, description="状态过滤"),
    page: int = Query(settings.DEFAULT_PAGE, ge=1, description="页码"),
    page_size: int = Query(
        settings.DEFAULT_PAGE_SIZE, ge=1, le=100, description="每页数量"
    ),
    user_id: str = Depends(get_current_user_id),
    service: GoalQueryService = Depends(get_goal_query_service),
) -> PaginatedResponse[GoalResponse]:
    """List all goals for current user."""
    result = await service.list_goals(
        user_id=user_id,
        status=status.value if status else None,
        page=page,
        page_size=page_size,
    )
    responses = [_to_goal_response(item) for item in result.items]

    return PaginatedResponse.create(
        items=responses,
        total=result.total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=ApiResponse[GoalResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建Goal",
    description="创建新的追踪目标",
)
async def create_goal(
    request: CreateGoalRequest,
    user_id: str = Depends(get_current_user_id),
    handler: CreateGoalHandler = Depends(get_create_goal_handler),
    query_service: GoalQueryService = Depends(get_goal_query_service),
) -> ApiResponse[GoalResponse]:
    """Create a new goal."""
    command = CreateGoalCommand(
        user_id=user_id,
        name=request.name,
        description=request.description,
        priority_mode=request.priority_mode.value,
        priority_terms=request.priority_terms,
        negative_terms=request.negative_terms,
        batch_windows=request.batch_windows,
        digest_send_time=request.digest_send_time,
    )
    goal = await handler.handle(command)

    response = await query_service.build_goal_data(goal)

    return ApiResponse.success(
        data=_to_goal_response(response),
        message="Goal created successfully",
    )


@router.post(
    "/suggest-keywords",
    response_model=ApiResponse[SuggestKeywordsResponse],
    summary="生成建议关键词",
    description="根据目标描述使用 AI 生成建议的优选关键词",
)
async def suggest_keywords(
    request: SuggestKeywordsRequest,
    user_id: str = Depends(get_current_user_id),
    service: KeywordSuggestionService = Depends(get_keyword_suggestion_service),
) -> ApiResponse[SuggestKeywordsResponse]:
    """Suggest keywords based on goal description using LLM."""
    keywords = await service.suggest_keywords(
        description=request.description,
        max_keywords=request.max_keywords,
    )
    get_business_logger().info(
        "goal_keywords_suggested",
        event_type="goal_keywords",
        user_id=user_id,
        description_len=len(request.description),
        keywords_count=len(keywords),
    )
    response = SuggestKeywordsResponse(keywords=keywords)
    return ApiResponse.success(data=response)


@router.post(
    "/generate-draft",
    response_model=ApiResponse[GenerateGoalDraftResponse],
    summary="AI 生成目标草稿",
    description="根据用户意图生成目标名称、描述和关键词（用于新建目标时快速填充）",
)
async def generate_goal_draft(
    request: GenerateGoalDraftRequest,
    user_id: str = Depends(get_current_user_id),
    service: GoalDraftService = Depends(get_goal_draft_service),
) -> ApiResponse[GenerateGoalDraftResponse]:
    """Generate a short goal draft based on user intent."""
    try:
        draft = await service.generate_draft(
            intent=request.intent,
            max_keywords=request.max_keywords,
        )
    except GoalDraftNotAvailableError as e:
        raise BizException(
            message="AI 功能暂不可用，请检查配置或稍后重试",
            code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="AI_NOT_AVAILABLE",
        ) from e
    except GoalDraftGenerationError as e:
        raise BizException(
            message="AI 生成失败，请稍后重试",
            code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="AI_GENERATION_FAILED",
        ) from e

    get_business_logger().info(
        "goal_draft_generated",
        event_type="goal_draft",
        user_id=user_id,
        intent_len=len(request.intent),
        keywords_count=len(draft.keywords),
    )

    response = GenerateGoalDraftResponse(
        name=draft.name,
        description=draft.description,
        keywords=draft.keywords,
    )
    return ApiResponse.success(data=response)


@router.get(
    "/{goal_id}",
    response_model=ApiResponse[GoalResponse],
    summary="获取Goal详情",
    description="获取单个Goal的详细信息",
)
async def get_goal(
    goal_id: str,
    user_id: str = Depends(get_current_user_id),
    service: GoalQueryService = Depends(get_goal_query_service),
) -> ApiResponse[GoalResponse]:
    """Get goal details."""
    response = await service.get_goal(goal_id=goal_id, user_id=user_id)
    return ApiResponse.success(data=_to_goal_response(response))


@router.put(
    "/{goal_id}",
    response_model=ApiResponse[GoalResponse],
    summary="更新Goal",
    description="更新Goal配置",
)
async def update_goal(
    goal_id: str,
    request: UpdateGoalRequest,
    user_id: str = Depends(get_current_user_id),
    handler: UpdateGoalHandler = Depends(get_update_goal_handler),
    query_service: GoalQueryService = Depends(get_goal_query_service),
) -> ApiResponse[GoalResponse]:
    """Update a goal."""
    command = UpdateGoalCommand(
        goal_id=goal_id,
        user_id=user_id,
        name=request.name,
        description=request.description,
        priority_mode=request.priority_mode.value if request.priority_mode else None,
        priority_terms=request.priority_terms,
        negative_terms=request.negative_terms,
        batch_windows=request.batch_windows,
        digest_send_time=request.digest_send_time,
    )
    goal = await handler.handle(command)

    response = await query_service.build_goal_data(goal)
    return ApiResponse.success(
        data=_to_goal_response(response),
        message="Goal updated successfully",
    )


@router.delete(
    "/{goal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除Goal",
    description="删除追踪目标（软删除）",
)
async def delete_goal(
    goal_id: str,
    user_id: str = Depends(get_current_user_id),
    handler: DeleteGoalHandler = Depends(get_delete_goal_handler),
) -> None:
    """Delete a goal (soft delete)."""
    command = DeleteGoalCommand(goal_id=goal_id, user_id=user_id)
    await handler.handle(command)


@router.post(
    "/{goal_id}/pause",
    response_model=GoalStatusResponse,
    summary="暂停Goal",
    description="暂停追踪目标",
)
async def pause_goal(
    goal_id: str,
    user_id: str = Depends(get_current_user_id),
    handler: PauseGoalHandler = Depends(get_pause_goal_handler),
) -> GoalStatusResponse:
    """Pause a goal."""
    command = PauseGoalCommand(goal_id=goal_id, user_id=user_id)
    goal = await handler.handle(command)
    return GoalStatusResponse(status=goal.status)


@router.post(
    "/{goal_id}/resume",
    response_model=GoalStatusResponse,
    summary="恢复Goal",
    description="恢复已暂停的追踪目标",
)
async def resume_goal(
    goal_id: str,
    user_id: str = Depends(get_current_user_id),
    handler: ResumeGoalHandler = Depends(get_resume_goal_handler),
) -> GoalStatusResponse:
    """Resume a goal."""
    command = ResumeGoalCommand(goal_id=goal_id, user_id=user_id)
    goal = await handler.handle(command)
    return GoalStatusResponse(status=goal.status)


class GoalMatchListResponse(PaginatedResponse[GoalItemMatchResponse]):
    """Goal match list response with pagination."""

    pass


@router.get(
    "/{goal_id}/matches",
    response_model=GoalMatchListResponse,
    summary="获取Goal的匹配Items",
    description="获取指定Goal匹配到的信息条目列表",
)
async def get_goal_matches(
    goal_id: str,
    min_score: float = Query(0.0, ge=0, le=1, description="最小匹配分数"),
    page: int = Query(settings.DEFAULT_PAGE, ge=1, description="页码"),
    page_size: int = Query(
        settings.DEFAULT_PAGE_SIZE, ge=1, le=100, description="每页数量"
    ),
    user_id: str = Depends(get_current_user_id),
    service: GoalMatchQueryService = Depends(get_goal_match_query_service),
) -> GoalMatchListResponse:
    """Get goal's matched items."""
    result = await service.list_matches(
        goal_id=goal_id,
        user_id=user_id,
        min_score=min_score,
        page=page,
        page_size=page_size,
    )

    responses = [
        GoalItemMatchResponse(
            id=item.id,
            goal_id=item.goal_id,
            item_id=item.item_id,
            match_score=item.match_score,
            features_json=item.features_json,
            reasons_json=item.reasons_json,
            computed_at=item.computed_at,
            item=ItemResponse(
                id=item.item.id,
                url=item.item.url,
                title=item.item.title,
                snippet=item.item.snippet,
                summary=item.item.summary,
                published_at=item.item.published_at,
                ingested_at=item.item.ingested_at,
                source_name=item.item.source_name,
            )
            if item.item
            else None,
        )
        for item in result.items
    ]

    return GoalMatchListResponse.create(
        items=responses,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )
