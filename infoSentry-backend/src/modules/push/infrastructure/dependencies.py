"""Push module dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.domain.events import get_event_bus
from src.core.infrastructure.database.session import get_db_session
from src.modules.push.infrastructure.mappers import (
    BlockedSourceMapper,
    ClickEventMapper,
    ItemFeedbackMapper,
    PushDecisionMapper,
)
from src.modules.push.infrastructure.repositories import (
    PostgreSQLBlockedSourceRepository,
    PostgreSQLClickEventRepository,
    PostgreSQLItemFeedbackRepository,
    PostgreSQLPushDecisionRepository,
)


def get_push_decision_mapper() -> PushDecisionMapper:
    return PushDecisionMapper()


def get_click_event_mapper() -> ClickEventMapper:
    return ClickEventMapper()


def get_item_feedback_mapper() -> ItemFeedbackMapper:
    return ItemFeedbackMapper()


def get_blocked_source_mapper() -> BlockedSourceMapper:
    return BlockedSourceMapper()


async def get_push_decision_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: PushDecisionMapper = Depends(get_push_decision_mapper),
) -> PostgreSQLPushDecisionRepository:
    return PostgreSQLPushDecisionRepository(session, mapper, get_event_bus())


async def get_click_event_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: ClickEventMapper = Depends(get_click_event_mapper),
) -> PostgreSQLClickEventRepository:
    return PostgreSQLClickEventRepository(session, mapper, get_event_bus())


async def get_item_feedback_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: ItemFeedbackMapper = Depends(get_item_feedback_mapper),
) -> PostgreSQLItemFeedbackRepository:
    return PostgreSQLItemFeedbackRepository(session, mapper, get_event_bus())


async def get_blocked_source_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: BlockedSourceMapper = Depends(get_blocked_source_mapper),
) -> PostgreSQLBlockedSourceRepository:
    return PostgreSQLBlockedSourceRepository(session, mapper, get_event_bus())
