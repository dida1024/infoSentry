"""Goal API routes."""

from fastapi import APIRouter, Depends, Query, status

from src.core.application.security import get_current_user_id
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
    get_goal_repository,
    get_pause_goal_handler,
    get_push_config_repository,
    get_resume_goal_handler,
    get_term_repository,
    get_update_goal_handler,
)
from src.modules.goals.application.handlers import (
    CreateGoalHandler,
    DeleteGoalHandler,
    PauseGoalHandler,
    ResumeGoalHandler,
    UpdateGoalHandler,
)
from src.modules.goals.domain.entities import Goal, TermType
from src.modules.goals.domain.exceptions import GoalNotFoundError
from src.modules.goals.domain.repository import (
    GoalPriorityTermRepository,
    GoalPushConfigRepository,
    GoalRepository,
)
from src.modules.goals.interfaces.schemas import (
    CreateGoalRequest,
    GoalResponse,
    GoalStatusResponse,
    UpdateGoalRequest,
)

router = APIRouter(prefix="/goals", tags=["goals"])


async def _build_goal_response(
    goal: Goal,
    push_config_repo: GoalPushConfigRepository,
    term_repo: GoalPriorityTermRepository,
) -> GoalResponse:
    """Build goal response with config and terms."""
    push_config = await push_config_repo.get_by_goal_id(goal.id)
    terms = await term_repo.list_by_goal(goal.id)

    priority_terms = [t.term for t in terms if t.term_type == TermType.MUST]
    negative_terms = [t.term for t in terms if t.term_type == TermType.NEGATIVE]

    return GoalResponse(
        id=goal.id,
        name=goal.name,
        description=goal.description,
        priority_mode=goal.priority_mode,
        status=goal.status,
        priority_terms=priority_terms if priority_terms else None,
        negative_terms=negative_terms if negative_terms else None,
        batch_windows=push_config.batch_windows if push_config else None,
        digest_send_time=push_config.digest_send_time if push_config else None,
        stats=None,
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
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: str = Depends(get_current_user_id),
    goal_repository: GoalRepository = Depends(get_goal_repository),
    push_config_repository: GoalPushConfigRepository = Depends(
        get_push_config_repository
    ),
    term_repository: GoalPriorityTermRepository = Depends(get_term_repository),
) -> PaginatedResponse[GoalResponse]:
    """List all goals for current user."""
    goals, total = await goal_repository.list_by_user(
        user_id=user_id,
        page=page,
        page_size=page_size,
    )

    responses = []
    for goal in goals:
        response = await _build_goal_response(
            goal, push_config_repository, term_repository
        )
        responses.append(response)

    return PaginatedResponse.create(
        items=responses,
        total=total,
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
    push_config_repository: GoalPushConfigRepository = Depends(
        get_push_config_repository
    ),
    term_repository: GoalPriorityTermRepository = Depends(get_term_repository),
) -> ApiResponse[GoalResponse]:
    """Create a new goal."""
    command = CreateGoalCommand(
        user_id=user_id,
        name=request.name,
        description=request.description,
        priority_mode=request.priority_mode,
        priority_terms=request.priority_terms,
        negative_terms=request.negative_terms,
        batch_windows=request.batch_windows,
        digest_send_time=request.digest_send_time,
    )
    goal = await handler.handle(command)

    response = await _build_goal_response(goal, push_config_repository, term_repository)

    return ApiResponse.success(data=response, message="Goal created successfully")


@router.get(
    "/{goal_id}",
    response_model=ApiResponse[GoalResponse],
    summary="获取Goal详情",
    description="获取单个Goal的详细信息",
)
async def get_goal(
    goal_id: str,
    user_id: str = Depends(get_current_user_id),
    goal_repository: GoalRepository = Depends(get_goal_repository),
    push_config_repository: GoalPushConfigRepository = Depends(
        get_push_config_repository
    ),
    term_repository: GoalPriorityTermRepository = Depends(get_term_repository),
) -> ApiResponse[GoalResponse]:
    """Get goal details."""
    goal = await goal_repository.get_by_id(goal_id)
    if not goal:
        raise GoalNotFoundError(goal_id)

    # Access check
    if goal.user_id != user_id:
        raise GoalNotFoundError(goal_id)

    response = await _build_goal_response(goal, push_config_repository, term_repository)

    return ApiResponse.success(data=response)


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
    push_config_repository: GoalPushConfigRepository = Depends(
        get_push_config_repository
    ),
    term_repository: GoalPriorityTermRepository = Depends(get_term_repository),
) -> ApiResponse[GoalResponse]:
    """Update a goal."""
    command = UpdateGoalCommand(
        goal_id=goal_id,
        user_id=user_id,
        name=request.name,
        description=request.description,
        priority_mode=request.priority_mode,
        priority_terms=request.priority_terms,
        negative_terms=request.negative_terms,
        batch_windows=request.batch_windows,
        digest_send_time=request.digest_send_time,
    )
    goal = await handler.handle(command)

    response = await _build_goal_response(goal, push_config_repository, term_repository)

    return ApiResponse.success(data=response, message="Goal updated successfully")


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
