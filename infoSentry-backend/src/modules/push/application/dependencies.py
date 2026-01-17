"""Push module application dependencies."""

from typing import NoReturn

from fastapi import Depends

from src.core.domain.ports.health_checker import EmailHealthChecker
from src.modules.goals.domain.repository import GoalRepository
from src.modules.items.domain.repository import ItemRepository
from src.modules.push.application.services import NotificationService
from src.modules.push.domain.repository import (
    BlockedSourceRepository,
    ClickEventRepository,
    ItemFeedbackRepository,
    PushDecisionRepository,
)
from src.modules.sources.domain.repository import SourceRepository


def _missing_dependency(name: str) -> NoReturn:
    raise RuntimeError(f"Missing dependency override for {name}")


async def get_push_decision_repository() -> PushDecisionRepository:
    _missing_dependency("PushDecisionRepository")


async def get_click_event_repository() -> ClickEventRepository:
    _missing_dependency("ClickEventRepository")


async def get_item_feedback_repository() -> ItemFeedbackRepository:
    _missing_dependency("ItemFeedbackRepository")


async def get_blocked_source_repository() -> BlockedSourceRepository:
    _missing_dependency("BlockedSourceRepository")


async def get_item_repository() -> ItemRepository:
    _missing_dependency("ItemRepository")


async def get_source_repository() -> SourceRepository:
    _missing_dependency("SourceRepository")


async def get_goal_repository() -> GoalRepository:
    _missing_dependency("GoalRepository")


async def get_email_health_checker() -> EmailHealthChecker:
    _missing_dependency("EmailHealthChecker")


async def get_notification_service(
    push_decision_repo: PushDecisionRepository = Depends(get_push_decision_repository),
    item_repo: ItemRepository = Depends(get_item_repository),
    source_repo: SourceRepository = Depends(get_source_repository),
    goal_repo: GoalRepository = Depends(get_goal_repository),
    feedback_repo: ItemFeedbackRepository = Depends(get_item_feedback_repository),
    blocked_source_repo: BlockedSourceRepository = Depends(
        get_blocked_source_repository
    ),
    click_repo: ClickEventRepository = Depends(get_click_event_repository),
) -> NotificationService:
    return NotificationService(
        push_decision_repo=push_decision_repo,
        item_repo=item_repo,
        source_repo=source_repo,
        goal_repo=goal_repo,
        feedback_repo=feedback_repo,
        blocked_source_repo=blocked_source_repo,
        click_repo=click_repo,
    )
