"""Push/Notification API routes."""

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse

from src.core.application.security import get_current_user_id
from src.modules.push.application.dependencies import get_notification_service
from src.modules.push.application.services import NotificationService
from src.modules.push.interfaces.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    NotificationListResponse,
    NotificationResponse,
)

router = APIRouter(tags=["notifications"])


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
    service: NotificationService = Depends(get_notification_service),
) -> NotificationListResponse:
    """List notifications for user."""
    result = await service.list_notifications(
        user_id=user_id,
        goal_id=goal_id,
        cursor=cursor,
        notification_status=notification_status,
    )

    return NotificationListResponse(
        notifications=[
            NotificationResponse(**n.model_dump()) for n in result.notifications
        ],
        next_cursor=result.next_cursor,
        has_more=result.has_more,
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
    service: NotificationService = Depends(get_notification_service),
):
    """Mark a notification as read."""
    await service.mark_notification_read(notification_id, user_id)
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
    service: NotificationService = Depends(get_notification_service),
) -> FeedbackResponse:
    """Submit feedback for an item."""
    feedback_id = await service.submit_feedback(
        item_id=item_id,
        goal_id=request.goal_id,
        feedback=request.feedback,
        block_source=request.block_source,
        user_id=user_id,
    )
    return FeedbackResponse(feedback_id=feedback_id)


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
    service: NotificationService = Depends(get_notification_service),
):
    """Track click and redirect to original URL."""
    target_url = await service.track_click(
        item_id=item_id,
        goal_id=goal_id,
        channel=channel,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    return RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)
