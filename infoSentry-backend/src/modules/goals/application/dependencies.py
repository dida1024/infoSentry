"""Goal module application dependencies.

Provides handlers and repositories without importing infrastructure.
"""

from typing import NoReturn

from fastapi import Depends

from src.core.application import dependencies as core_app_deps
from src.core.domain.ports.prompt_store import PromptStore
from src.modules.goals.application.goal_draft_service import GoalDraftService
from src.modules.goals.application.handlers import (
    ArchiveGoalHandler,
    CreateGoalHandler,
    DeleteGoalHandler,
    PauseGoalHandler,
    ResumeGoalHandler,
    UpdateGoalHandler,
)
from src.modules.goals.application.keyword_service import KeywordSuggestionService
from src.modules.goals.application.services import (
    GoalMatchQueryService,
    GoalQueryService,
)
from src.modules.goals.domain.repository import (
    GoalPriorityTermRepository,
    GoalPushConfigRepository,
    GoalRepository,
)
from src.modules.items.application.dependencies import (
    get_goal_item_match_repository,
    get_item_repository,
)
from src.modules.items.domain.repository import GoalItemMatchRepository, ItemRepository
from src.modules.sources.application.dependencies import get_source_repository
from src.modules.sources.domain.repository import SourceRepository


def _missing_dependency(name: str) -> NoReturn:
    raise RuntimeError(f"Missing dependency override for {name}")


async def get_goal_repository() -> GoalRepository:
    _missing_dependency("GoalRepository")


async def get_push_config_repository() -> GoalPushConfigRepository:
    _missing_dependency("GoalPushConfigRepository")


async def get_term_repository() -> GoalPriorityTermRepository:
    _missing_dependency("GoalPriorityTermRepository")


async def get_create_goal_handler(
    goal_repository: GoalRepository = Depends(get_goal_repository),
    push_config_repository: GoalPushConfigRepository = Depends(
        get_push_config_repository
    ),
    term_repository: GoalPriorityTermRepository = Depends(get_term_repository),
) -> CreateGoalHandler:
    return CreateGoalHandler(goal_repository, push_config_repository, term_repository)


async def get_update_goal_handler(
    goal_repository: GoalRepository = Depends(get_goal_repository),
    push_config_repository: GoalPushConfigRepository = Depends(
        get_push_config_repository
    ),
    term_repository: GoalPriorityTermRepository = Depends(get_term_repository),
) -> UpdateGoalHandler:
    return UpdateGoalHandler(goal_repository, push_config_repository, term_repository)


async def get_pause_goal_handler(
    goal_repository: GoalRepository = Depends(get_goal_repository),
) -> PauseGoalHandler:
    return PauseGoalHandler(goal_repository)


async def get_resume_goal_handler(
    goal_repository: GoalRepository = Depends(get_goal_repository),
) -> ResumeGoalHandler:
    return ResumeGoalHandler(goal_repository)


async def get_archive_goal_handler(
    goal_repository: GoalRepository = Depends(get_goal_repository),
) -> ArchiveGoalHandler:
    return ArchiveGoalHandler(goal_repository)


async def get_delete_goal_handler(
    goal_repository: GoalRepository = Depends(get_goal_repository),
) -> DeleteGoalHandler:
    return DeleteGoalHandler(goal_repository)


async def get_goal_match_query_service(
    goal_repository: GoalRepository = Depends(get_goal_repository),
    match_repository: GoalItemMatchRepository = Depends(get_goal_item_match_repository),
    item_repository: ItemRepository = Depends(get_item_repository),
    source_repository: SourceRepository = Depends(get_source_repository),
) -> GoalMatchQueryService:
    return GoalMatchQueryService(
        goal_repository=goal_repository,
        match_repository=match_repository,
        item_repository=item_repository,
        source_repository=source_repository,
    )


async def get_goal_query_service(
    goal_repository: GoalRepository = Depends(get_goal_repository),
    push_config_repository: GoalPushConfigRepository = Depends(
        get_push_config_repository
    ),
    term_repository: GoalPriorityTermRepository = Depends(get_term_repository),
) -> GoalQueryService:
    return GoalQueryService(
        goal_repository=goal_repository,
        push_config_repository=push_config_repository,
        term_repository=term_repository,
    )


async def get_keyword_suggestion_service(
    prompt_store: PromptStore = Depends(core_app_deps.get_prompt_store),
) -> KeywordSuggestionService:
    """获取关键词建议服务。"""
    return KeywordSuggestionService(prompt_store=prompt_store)


async def get_goal_draft_service(
    prompt_store: PromptStore = Depends(core_app_deps.get_prompt_store),
) -> GoalDraftService:
    """获取目标草稿生成服务。"""
    return GoalDraftService(prompt_store=prompt_store)
