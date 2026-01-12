"""Items module application dependencies."""

from typing import NoReturn

from src.modules.items.domain.repository import GoalItemMatchRepository, ItemRepository


def _missing_dependency(name: str) -> NoReturn:
    raise RuntimeError(f"Missing dependency override for {name}")


async def get_item_repository() -> ItemRepository:
    _missing_dependency("ItemRepository")


async def get_goal_item_match_repository() -> GoalItemMatchRepository:
    _missing_dependency("GoalItemMatchRepository")
