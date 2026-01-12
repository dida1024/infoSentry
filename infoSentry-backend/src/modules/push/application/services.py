"""Push application services."""

import base64
from datetime import datetime

from loguru import logger

from src.core.domain.exceptions import EntityNotFoundError
from src.modules.goals.domain.exceptions import GoalNotFoundError
from src.modules.goals.domain.repository import GoalRepository
from src.modules.items.domain.repository import ItemRepository
from src.modules.push.application.models import (
    ActionData,
    EvidenceItemData,
    ItemSummaryData,
    NotificationData,
    NotificationListData,
    ReasonData,
)
from src.modules.push.domain.entities import (
    BlockedSource,
    ClickEvent,
    ItemFeedback,
    PushChannel,
    PushStatus,
)
from src.modules.push.domain.repository import (
    BlockedSourceRepository,
    ClickEventRepository,
    ItemFeedbackRepository,
    PushDecisionRepository,
)
from src.modules.sources.domain.repository import SourceRepository


def _decode_cursor(cursor: str | None) -> tuple[int, int]:
    if not cursor:
        return 1, 20
    try:
        decoded = base64.b64decode(cursor).decode()
        page, page_size = decoded.split(":")
        return int(page), int(page_size)
    except Exception as e:
        logger.debug(f"Failed to decode cursor '{cursor}', using defaults: {e}")
        return 1, 20


def _encode_cursor(page: int, page_size: int) -> str:
    return base64.b64encode(f"{page}:{page_size}".encode()).decode()


class NotificationService:
    """Notification query and action service."""

    def __init__(
        self,
        push_decision_repo: PushDecisionRepository,
        item_repo: ItemRepository,
        source_repo: SourceRepository,
        goal_repo: GoalRepository,
        feedback_repo: ItemFeedbackRepository,
        blocked_source_repo: BlockedSourceRepository,
        click_repo: ClickEventRepository,
    ) -> None:
        self.push_decision_repo = push_decision_repo
        self.item_repo = item_repo
        self.source_repo = source_repo
        self.goal_repo = goal_repo
        self.feedback_repo = feedback_repo
        self.blocked_source_repo = blocked_source_repo
        self.click_repo = click_repo

    async def list_notifications(
        self,
        user_id: str,
        goal_id: str | None,
        cursor: str | None,
        notification_status: str | None,
    ) -> NotificationListData:
        page, page_size = _decode_cursor(cursor)

        status_filter = None
        if notification_status:
            try:
                status_filter = PushStatus(notification_status)
            except ValueError:
                status_filter = None

        if goal_id:
            goal = await self.goal_repo.get_by_id(goal_id)
            if not goal or goal.user_id != user_id:
                raise GoalNotFoundError(goal_id)

            decisions, total = await self.push_decision_repo.list_by_goal(
                goal_id=goal_id,
                status=status_filter,
                page=page,
                page_size=page_size,
            )
        else:
            goals, _ = await self.goal_repo.list_by_user(
                user_id=user_id,
                page=1,
                page_size=100,
            )
            if not goals:
                return NotificationListData(
                    notifications=[],
                    next_cursor=None,
                    has_more=False,
                )

            goal_ids = [g.id for g in goals]
            decisions, total = await self.push_decision_repo.list_by_goals(
                goal_ids=goal_ids,
                status=status_filter,
                page=page,
                page_size=page_size,
            )

        notifications: list[NotificationData] = []

        for decision in decisions:
            item = await self.item_repo.get_by_id(decision.item_id)
            if not item:
                continue

            source_name = None
            source = await self.source_repo.get_by_id(item.source_id)
            if source:
                source_name = source.name

            item_summary = ItemSummaryData(
                title=item.title,
                url=item.url,
                source_name=source_name,
                published_at=item.published_at,
                snippet=item.snippet,
            )

            reason = None
            if decision.reason_json:
                evidence_list = []
                for ev in decision.reason_json.get("evidence", []):
                    evidence_list.append(
                        EvidenceItemData(
                            type=ev.get("type", "UNKNOWN"),
                            value=ev.get("value", ""),
                            quote=ev.get("quote"),
                            ref=ev.get("ref"),
                        )
                    )
                reason = ReasonData(
                    summary=decision.reason_json.get("summary", ""),
                    score=decision.reason_json.get("score", 0.0),
                    evidence=evidence_list,
                )

            actions = [
                ActionData(
                    type="OPEN",
                    url=f"/r/{item.id}?goal_id={decision.goal_id}&channel=email",
                ),
                ActionData(type="LIKE", url=None),
                ActionData(type="DISLIKE", url=None),
                ActionData(type="BLOCK_SOURCE", url=None),
            ]

            notifications.append(
                NotificationData(
                    id=decision.id,
                    goal_id=decision.goal_id,
                    item_id=decision.item_id,
                    decision=decision.decision,
                    status=decision.status,
                    channel=decision.channel,
                    item=item_summary,
                    reason=reason,
                    actions=actions,
                    decided_at=decision.decided_at,
                    sent_at=decision.sent_at,
                )
            )

        has_more = (page * page_size) < total
        next_cursor = _encode_cursor(page + 1, page_size) if has_more else None

        return NotificationListData(
            notifications=notifications,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def mark_notification_read(self, notification_id: str, user_id: str) -> None:
        decision = await self.push_decision_repo.get_by_id(notification_id)
        if not decision:
            raise EntityNotFoundError("Notification", notification_id)

        goal = await self.goal_repo.get_by_id(decision.goal_id)
        if not goal or goal.user_id != user_id:
            raise GoalNotFoundError(decision.goal_id)

        decision.mark_read()
        await self.push_decision_repo.update(decision)

    async def submit_feedback(
        self,
        item_id: str,
        goal_id: str,
        feedback: str,
        block_source: bool,
        user_id: str,
    ) -> str:
        item = await self.item_repo.get_by_id(item_id)
        if not item:
            raise EntityNotFoundError("Item", item_id)

        goal = await self.goal_repo.get_by_id(goal_id)
        if not goal or goal.user_id != user_id:
            raise GoalNotFoundError(goal_id)

        existing = await self.feedback_repo.get_by_item_goal_user(
            item_id=item_id,
            goal_id=goal_id,
            user_id=user_id,
        )

        if existing:
            existing.feedback = feedback
            existing.block_source = block_source
            saved = await self.feedback_repo.update(existing)
        else:
            saved = await self.feedback_repo.create(
                ItemFeedback(
                    item_id=item_id,
                    goal_id=goal_id,
                    user_id=user_id,
                    feedback=feedback,
                    block_source=block_source,
                )
            )

        if block_source:
            is_blocked = await self.blocked_source_repo.is_blocked(
                user_id=user_id,
                source_id=item.source_id,
                goal_id=goal_id,
            )
            if not is_blocked:
                blocked = BlockedSource(
                    user_id=user_id,
                    goal_id=goal_id,
                    source_id=item.source_id,
                    blocked_at=datetime.now(),
                )
                await self.blocked_source_repo.create(blocked)

        return saved.id

    async def track_click(
        self,
        item_id: str,
        goal_id: str | None,
        channel: str | None,
        user_agent: str | None,
        ip_address: str | None,
    ) -> str:
        item = await self.item_repo.get_by_id(item_id)
        if not item:
            raise EntityNotFoundError("Item", item_id)

        push_channel = PushChannel.EMAIL
        if channel == "in_app":
            push_channel = PushChannel.IN_APP

        click_event = ClickEvent(
            item_id=item_id,
            goal_id=goal_id,
            channel=push_channel,
            clicked_at=datetime.now(),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await self.click_repo.create(click_event)

        return item.url
