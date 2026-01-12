"""Goal module application dependencies.

Provides handlers and repositories without importing infrastructure.
"""

from typing import NoReturn

from fastapi import Depends

from src.modules.goals.application.handlers import (
    ArchiveGoalHandler,
    CreateGoalHandler,
    DeleteGoalHandler,
    PauseGoalHandler,
    ResumeGoalHandler,
    UpdateGoalHandler,
)
from src.modules.goals.domain.repository import (
    GoalPriorityTermRepository,
    GoalPushConfigRepository,
    GoalRepository,
)


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
