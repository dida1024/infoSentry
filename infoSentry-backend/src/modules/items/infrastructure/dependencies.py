"""Items module dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.domain.events import get_event_bus
from src.core.infrastructure.database.session import get_db_session
from src.modules.items.infrastructure.mappers import GoalItemMatchMapper, ItemMapper
from src.modules.items.infrastructure.repositories import (
    PostgreSQLGoalItemMatchRepository,
    PostgreSQLItemRepository,
)


def get_item_mapper() -> ItemMapper:
    return ItemMapper()


def get_goal_item_match_mapper() -> GoalItemMatchMapper:
    return GoalItemMatchMapper()


async def get_item_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: ItemMapper = Depends(get_item_mapper),
) -> PostgreSQLItemRepository:
    return PostgreSQLItemRepository(session, mapper, get_event_bus())


async def get_goal_item_match_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: GoalItemMatchMapper = Depends(get_goal_item_match_mapper),
) -> PostgreSQLGoalItemMatchRepository:
    return PostgreSQLGoalItemMatchRepository(session, mapper, get_event_bus())
