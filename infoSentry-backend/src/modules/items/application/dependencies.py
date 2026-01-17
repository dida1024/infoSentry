"""Items module application dependencies."""

from typing import NoReturn

from src.core.domain.ports.business_logger import BusinessEventLogger
from src.core.domain.ports.kv import KVClient
from src.modules.items.domain.repository import GoalItemMatchRepository, ItemRepository


def _missing_dependency(name: str) -> NoReturn:
    raise RuntimeError(f"Missing dependency override for {name}")


async def get_item_repository() -> ItemRepository:
    _missing_dependency("ItemRepository")


async def get_goal_item_match_repository() -> GoalItemMatchRepository:
    _missing_dependency("GoalItemMatchRepository")


async def get_business_event_logger() -> BusinessEventLogger:
    _missing_dependency("BusinessEventLogger")


async def get_kv_client() -> KVClient:
    _missing_dependency("KVClient")
