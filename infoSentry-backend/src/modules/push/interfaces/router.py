"""Push/Notification API routes."""

import base64
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from src.core.infrastructure.security.jwt import get_current_user_id
from src.modules.goals.domain.exceptions import GoalNotFoundError
from src.modules.goals.infrastructure.dependencies import get_goal_repository
from src.modules.goals.infrastructure.repositories import PostgreSQLGoalRepository
from src.modules.items.infrastructure.dependencies import get_item_repository
from src.modules.items.infrastructure.repositories import PostgreSQLItemRepository
from src.modules.push.domain.entities import (
    BlockedSource,
    ClickEvent,
    ItemFeedback,
    PushChannel,
    PushStatus,
)
from src.modules.push.infrastructure.dependencies import (
    get_blocked_source_repository,
    get_click_event_repository,
    get_item_feedback_repository,
    get_push_decision_repository,
)
from src.modules.push.infrastructure.repositories import (
    PostgreSQLBlockedSourceRepository,
    PostgreSQLClickEventRepository,
    PostgreSQLItemFeedbackRepository,
    PostgreSQLPushDecisionRepository,
)
from src.modules.push.interfaces.schemas import (
    ActionResponse,
    EvidenceItem,
    FeedbackRequest,
    FeedbackResponse,
    ItemSummaryResponse,
    NotificationListResponse,
    NotificationResponse,
    ReasonResponse,
)
from src.modules.sources.infrastructure.dependencies import get_source_repository
from src.modules.sources.infrastructure.repositories import PostgreSQLSourceRepository

router = APIRouter(tags=["notifications"])


def _decode_cursor(cursor: str | None) -> tuple[int, int]:
    """Decode cursor to (page, page_size)."""
    if not cursor:
        return 1, 20
    try:
        decoded = base64.b64decode(cursor).decode()
        page, page_size = decoded.split(":")
        return int(page), int(page_size)
    except Exception:
        return 1, 20


def _encode_cursor(page: int, page_size: int) -> str:
    """Encode (page, page_size) to cursor."""
    return base64.b64encode(f"{page}:{page_size}".encode()).decode()


@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    summary="获取通知列表",
    description="获取推送通知列表，支持分页和过滤",
)
async def list_notifications(
    goal_id: str | None = Query(None, description="Goal ID过滤"),
    cursor: str | None = Query(None, description="分页游标"),
    notification_status: str | None = Query(
        None, alias="status", description="状态过滤"
    ),
    user_id: str = Depends(get_current_user_id),
    push_decision_repo: PostgreSQLPushDecisionRepository = Depends(
        get_push_decision_repository
    ),
    item_repo: PostgreSQLItemRepository = Depends(get_item_repository),
    source_repo: PostgreSQLSourceRepository = Depends(get_source_repository),
    goal_repo: PostgreSQLGoalRepository = Depends(get_goal_repository),
) -> NotificationListResponse:
    """List notifications for user."""
    page, page_size = _decode_cursor(cursor)

    # Parse status filter
    status_filter = None
    if notification_status:
        try:
            status_filter = PushStatus(notification_status)
        except ValueError:
            pass

    notifications: list[NotificationResponse] = []

    # If goal_id is provided, filter by that goal
    if goal_id:
        # Verify goal belongs to user
        goal = await goal_repo.get_by_id(goal_id)
        if not goal or goal.user_id != user_id:
            raise GoalNotFoundError(goal_id)

        decisions, total = await push_decision_repo.list_by_goal(
            goal_id=goal_id,
            status=status_filter,
            page=page,
            page_size=page_size,
        )
    else:
        # Get all goals for user and fetch decisions in batch
        goals, _ = await goal_repo.list_by_user(user_id=user_id, page=1, page_size=100)
        if not goals:
            return NotificationListResponse(
                notifications=[], next_cursor=None, has_more=False
            )

        # Fetch decisions for all user goals in a single query
        goal_ids = [g.id for g in goals]
        decisions, total = await push_decision_repo.list_by_goals(
            goal_ids=goal_ids,
            status=status_filter,
            page=page,
            page_size=page_size,
        )

    # Build notification responses
    for decision in decisions:
        # Get item details
        item = await item_repo.get_by_id(decision.item_id)
        if not item:
            continue

        # Get source name
        source_name = None
        source = await source_repo.get_by_id(item.source_id)
        if source:
            source_name = source.name

        # Build item summary
        item_summary = ItemSummaryResponse(
            title=item.title,
            url=item.url,
            source_name=source_name,
            published_at=item.published_at,
            snippet=item.snippet,
        )

        # Build reason from reason_json
        reason = None
        if decision.reason_json:
            evidence_list = []
            for ev in decision.reason_json.get("evidence", []):
                evidence_list.append(
                    EvidenceItem(
                        type=ev.get("type", "UNKNOWN"),
                        value=ev.get("value", ""),
                        quote=ev.get("quote"),
                        ref=ev.get("ref"),
                    )
                )
            reason = ReasonResponse(
                summary=decision.reason_json.get("summary", ""),
                score=decision.reason_json.get("score", 0.0),
                evidence=evidence_list,
            )

        # Build actions
        actions = [
            ActionResponse(
                type="OPEN",
                url=f"/r/{item.id}?goal_id={decision.goal_id}&channel=email",
            ),
            ActionResponse(type="LIKE", url=None),
            ActionResponse(type="DISLIKE", url=None),
            ActionResponse(type="BLOCK_SOURCE", url=None),
        ]

        notifications.append(
            NotificationResponse(
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

    # Determine if there are more results
    has_more = (page * page_size) < total
    next_cursor = _encode_cursor(page + 1, page_size) if has_more else None

    return NotificationListResponse(
        notifications=notifications,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.post(
    "/notifications/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="标记已读",
    description="将通知标记为已读",
)
async def mark_notification_read(
    notification_id: str,
    user_id: str = Depends(get_current_user_id),
    push_decision_repo: PostgreSQLPushDecisionRepository = Depends(
        get_push_decision_repository
    ),
    goal_repo: PostgreSQLGoalRepository = Depends(get_goal_repository),
):
    """Mark a notification as read."""
    # Get the decision
    decision = await push_decision_repo.get_by_id(notification_id)
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Notification not found"},
        )

    # Verify goal belongs to user
    goal = await goal_repo.get_by_id(decision.goal_id)
    if not goal or goal.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Notification not found"},
        )

    # Mark as read
    decision.mark_read()
    await push_decision_repo.update(decision)

    return None


@router.post(
    "/items/{item_id}/feedback",
    response_model=FeedbackResponse,
    summary="提交反馈",
    description="对条目提交反馈（like/dislike）",
)
async def submit_feedback(
    item_id: str,
    request: FeedbackRequest,
    user_id: str = Depends(get_current_user_id),
    item_repo: PostgreSQLItemRepository = Depends(get_item_repository),
    goal_repo: PostgreSQLGoalRepository = Depends(get_goal_repository),
    feedback_repo: PostgreSQLItemFeedbackRepository = Depends(
        get_item_feedback_repository
    ),
    blocked_source_repo: PostgreSQLBlockedSourceRepository = Depends(
        get_blocked_source_repository
    ),
) -> FeedbackResponse:
    """Submit feedback for an item."""
    # Verify item exists
    item = await item_repo.get_by_id(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Item not found"},
        )

    # Verify goal belongs to user
    goal = await goal_repo.get_by_id(request.goal_id)
    if not goal or goal.user_id != user_id:
        raise GoalNotFoundError(request.goal_id)

    # Check if feedback already exists
    existing = await feedback_repo.get_by_item_goal_user(
        item_id=item_id,
        goal_id=request.goal_id,
        user_id=user_id,
    )

    if existing:
        # Update existing feedback
        existing.feedback = request.feedback
        existing.block_source = request.block_source
        feedback = await feedback_repo.update(existing)
    else:
        # Create new feedback
        feedback = ItemFeedback(
            item_id=item_id,
            goal_id=request.goal_id,
            user_id=user_id,
            feedback=request.feedback,
            block_source=request.block_source,
        )
        feedback = await feedback_repo.create(feedback)

    # If block_source is True, add to blocked sources
    if request.block_source:
        # Check if already blocked
        is_blocked = await blocked_source_repo.is_blocked(
            user_id=user_id,
            source_id=item.source_id,
            goal_id=request.goal_id,
        )
        if not is_blocked:
            blocked = BlockedSource(
                user_id=user_id,
                goal_id=request.goal_id,
                source_id=item.source_id,
                blocked_at=datetime.now(),
            )
            await blocked_source_repo.create(blocked)

    return FeedbackResponse(feedback_id=feedback.id)


@router.get(
    "/r/{item_id}",
    response_class=RedirectResponse,
    status_code=status.HTTP_302_FOUND,
    summary="点击跟踪重定向",
    description="记录点击事件并重定向到原文",
)
async def redirect_click(
    item_id: str,
    request: Request,
    goal_id: str | None = Query(None, description="Goal ID"),
    channel: str | None = Query(None, description="来源渠道"),
    item_repo: PostgreSQLItemRepository = Depends(get_item_repository),
    click_repo: PostgreSQLClickEventRepository = Depends(get_click_event_repository),
):
    """Track click and redirect to original URL."""
    # Get item
    item = await item_repo.get_by_id(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Item not found"},
        )

    # Determine channel
    push_channel = PushChannel.EMAIL
    if channel == "in_app":
        push_channel = PushChannel.IN_APP

    # Record click event
    click_event = ClickEvent(
        item_id=item_id,
        goal_id=goal_id,
        channel=push_channel,
        clicked_at=datetime.now(),
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    await click_repo.create(click_event)

    # Redirect to original URL
    return RedirectResponse(url=item.url, status_code=status.HTTP_302_FOUND)
