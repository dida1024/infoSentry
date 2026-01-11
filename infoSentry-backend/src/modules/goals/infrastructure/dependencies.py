"""Goal module dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.domain.events import get_event_bus
from src.core.infrastructure.database.session import get_db_session
from src.modules.goals.application.handlers import (
    ArchiveGoalHandler,
    CreateGoalHandler,
    DeleteGoalHandler,
    PauseGoalHandler,
    ResumeGoalHandler,
    UpdateGoalHandler,
)
from src.modules.goals.infrastructure.mappers import (
    GoalMapper,
    GoalPriorityTermMapper,
    GoalPushConfigMapper,
)
from src.modules.goals.infrastructure.repositories import (
    PostgreSQLGoalPriorityTermRepository,
    PostgreSQLGoalPushConfigRepository,
    PostgreSQLGoalRepository,
)


def get_goal_mapper() -> GoalMapper:
    return GoalMapper()


def get_push_config_mapper() -> GoalPushConfigMapper:
    return GoalPushConfigMapper()


def get_term_mapper() -> GoalPriorityTermMapper:
    return GoalPriorityTermMapper()


async def get_goal_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: GoalMapper = Depends(get_goal_mapper),
) -> PostgreSQLGoalRepository:
    return PostgreSQLGoalRepository(session, mapper, get_event_bus())


async def get_push_config_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: GoalPushConfigMapper = Depends(get_push_config_mapper),
) -> PostgreSQLGoalPushConfigRepository:
    return PostgreSQLGoalPushConfigRepository(session, mapper, get_event_bus())


async def get_term_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: GoalPriorityTermMapper = Depends(get_term_mapper),
) -> PostgreSQLGoalPriorityTermRepository:
    return PostgreSQLGoalPriorityTermRepository(session, mapper, get_event_bus())


async def get_create_goal_handler(
    goal_repository: PostgreSQLGoalRepository = Depends(get_goal_repository),
    push_config_repository: PostgreSQLGoalPushConfigRepository = Depends(
        get_push_config_repository
    ),
    term_repository: PostgreSQLGoalPriorityTermRepository = Depends(
        get_term_repository
    ),
) -> CreateGoalHandler:
    return CreateGoalHandler(goal_repository, push_config_repository, term_repository)


async def get_update_goal_handler(
    goal_repository: PostgreSQLGoalRepository = Depends(get_goal_repository),
    push_config_repository: PostgreSQLGoalPushConfigRepository = Depends(
        get_push_config_repository
    ),
    term_repository: PostgreSQLGoalPriorityTermRepository = Depends(
        get_term_repository
    ),
) -> UpdateGoalHandler:
    return UpdateGoalHandler(goal_repository, push_config_repository, term_repository)


async def get_pause_goal_handler(
    goal_repository: PostgreSQLGoalRepository = Depends(get_goal_repository),
) -> PauseGoalHandler:
    return PauseGoalHandler(goal_repository)


async def get_resume_goal_handler(
    goal_repository: PostgreSQLGoalRepository = Depends(get_goal_repository),
) -> ResumeGoalHandler:
    return ResumeGoalHandler(goal_repository)


async def get_archive_goal_handler(
    goal_repository: PostgreSQLGoalRepository = Depends(get_goal_repository),
) -> ArchiveGoalHandler:
    return ArchiveGoalHandler(goal_repository)


async def get_delete_goal_handler(
    goal_repository: PostgreSQLGoalRepository = Depends(get_goal_repository),
) -> DeleteGoalHandler:
    return DeleteGoalHandler(goal_repository)
