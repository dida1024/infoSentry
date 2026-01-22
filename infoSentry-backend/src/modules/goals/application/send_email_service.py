"""Goal email sending service.

Provides functionality to manually send goal push emails on demand.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from loguru import logger

from src.core.config import settings
from src.core.infrastructure.logging import get_business_logger
from src.core.infrastructure.redis.client import RedisClient
from src.modules.goals.domain.repository import GoalRepository
from src.modules.items.domain.entities import GoalItemMatch
from src.modules.items.domain.repository import GoalItemMatchRepository, ItemRepository
from src.modules.push.application.email_service import EmailService, get_email_service
from src.modules.push.application.email_templates import (
    EmailData,
    EmailItem,
    build_redirect_url,
    render_digest_email,
    render_plain_text_fallback,
)
from src.modules.push.domain.entities import (
    PushChannel,
    PushDecision,
    PushDecisionRecord,
    PushStatus,
)
from src.modules.push.domain.repository import PushDecisionRepository
from src.modules.sources.domain.repository import SourceRepository
from src.modules.users.domain.repository import UserRepository


class GoalNotFoundError(Exception):
    """Goal not found or access denied."""


class NoItemsToSendError(Exception):
    """No items available to send."""


class RateLimitExceededError(Exception):
    """Rate limit exceeded for this operation."""


class UserNoEmailError(Exception):
    """User has no email address configured."""


class EmailServiceUnavailableError(Exception):
    """Email service is not available."""


@dataclass
class SendEmailResult:
    """Result of send email operation."""

    success: bool
    email_sent: bool
    items_count: int
    decisions_updated: int
    preview_subject: str | None = None
    preview_to_email: str | None = None
    preview_item_titles: list[str] | None = None
    message: str = ""


class GoalSendEmailService:
    """Service for manually sending goal push emails.

    Features:
    - Send emails for all unsent matched items
    - Rate limiting (5 per hour per goal)
    - Dry run mode for preview
    - Updates push_decision status to SENT
    """

    RATE_LIMIT_RESOURCE = "goal_email"
    RATE_LIMIT_PER_HOUR = 5
    DEFAULT_LOOKBACK_HOURS = 24

    def __init__(
        self,
        goal_repo: GoalRepository,
        user_repo: UserRepository,
        match_repo: GoalItemMatchRepository,
        item_repo: ItemRepository,
        source_repo: SourceRepository,
        decision_repo: PushDecisionRepository,
        redis_client: RedisClient,
        email_service: EmailService | None = None,
    ):
        self.goal_repo = goal_repo
        self.user_repo = user_repo
        self.match_repo = match_repo
        self.item_repo = item_repo
        self.source_repo = source_repo
        self.decision_repo = decision_repo
        self.redis = redis_client
        self.email_service = email_service or get_email_service()

    async def send_immediately(
        self,
        goal_id: str,
        user_id: str,
        since: datetime | None = None,
        min_score: float = 0.0,
        limit: int = 20,
        include_sent: bool = False,
        dry_run: bool = False,
    ) -> SendEmailResult:
        """Send goal email immediately.

        Args:
            goal_id: Goal to send email for
            user_id: Current user ID (for access control)
            since: Only include items matched since this time
            min_score: Minimum match score filter
            limit: Maximum items to include
            include_sent: Include items that already have SENT status
            dry_run: Preview only, do not send or update status

        Returns:
            SendEmailResult with operation details

        Raises:
            GoalNotFoundError: Goal not found or user doesn't own it
            NoItemsToSendError: No items to send
            RateLimitExceededError: Rate limit exceeded
            UserNoEmailError: User has no email
            EmailServiceUnavailableError: Email service unavailable
        """
        # 1. Validate goal ownership
        goal = await self.goal_repo.get_by_id(goal_id)
        if not goal or goal.user_id != user_id:
            raise GoalNotFoundError(f"Goal {goal_id} not found")

        # 2. Check rate limit (skip for dry_run). Only increment after success.
        window: str | None = None
        identifier: str | None = None
        if not dry_run:
            window = datetime.now(UTC).strftime("%Y%m%d%H")
            identifier = f"{user_id}:{goal_id}"
            current = await self.redis.get_rate_limit_count(
                resource=self.RATE_LIMIT_RESOURCE,
                identifier=identifier,
                window=window,
            )
            if current >= self.RATE_LIMIT_PER_HOUR:
                raise RateLimitExceededError(
                    f"Rate limit exceeded: {current}/{self.RATE_LIMIT_PER_HOUR} per hour"
                )

        # 3. Get user email
        user = await self.user_repo.get_by_id(goal.user_id)
        if not user or not user.email:
            raise UserNoEmailError("User has no email configured")

        # 4. Query unsent matches
        since = since or (
            datetime.now(UTC) - timedelta(hours=self.DEFAULT_LOOKBACK_HOURS)
        )
        matches_with_decisions = await self.match_repo.list_unsent_matches(
            goal_id=goal_id,
            min_score=min_score,
            since=since,
            limit=limit,
            include_sent=include_sent,
        )

        if not matches_with_decisions:
            raise NoItemsToSendError(f"No items to send for goal {goal_id}")

        # 5. Build email items
        email_items = await self._build_email_items(matches_with_decisions, goal_id)

        # Build email data
        email_data = EmailData(
            to_email=user.email,
            goal_id=goal_id,
            goal_name=goal.name,
            items=email_items,
            decision_ids=[],  # Will be populated after creating/updating decisions
        )

        # Generate email content
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        subject, html_body = render_digest_email(
            data=email_data,
            date_str=date_str,
            base_url=settings.BACKEND_HOST,
        )
        # Modify subject to indicate manual trigger
        subject = f"📬 [手动] 目标推送: {goal.name}"

        # 6. Dry run - return preview
        if dry_run:
            return SendEmailResult(
                success=True,
                email_sent=False,
                items_count=len(email_items),
                decisions_updated=0,
                preview_subject=subject,
                preview_to_email=user.email,
                preview_item_titles=[item.title for item in email_items],
                message="预览生成成功",
            )

        # 7. Check email service availability
        if not self.email_service.is_available():
            raise EmailServiceUnavailableError("Email service is not available")

        # 8. Send email
        plain_body = render_plain_text_fallback(email_data)
        result = await self.email_service.send_email(
            to_email=user.email,
            subject=subject,
            html_body=html_body,
            plain_body=plain_body,
        )

        if not result.success:
            # Don't update decisions if email failed
            logger.error(f"Failed to send goal email: {result.error}")
            return SendEmailResult(
                success=False,
                email_sent=False,
                items_count=len(email_items),
                decisions_updated=0,
                message=f"邮件发送失败: {result.error}",
            )

        # 9. Update rate limit count (successful sends only)
        if window and identifier:
            allowed, count = await self.redis.rate_limit_check(
                resource=self.RATE_LIMIT_RESOURCE,
                identifier=identifier,
                window=window,
                limit=self.RATE_LIMIT_PER_HOUR,
                ttl=3600,
            )
            if not allowed:
                get_business_logger().warning(
                    "goal_email_rate_limit_exceeded_after_send",
                    event_type="goal_email",
                    goal_id=goal_id,
                    user_id=user_id,
                    current=count,
                    limit=self.RATE_LIMIT_PER_HOUR,
                )

        # 10. Update/create push decisions
        decisions_updated = await self._update_push_decisions(
            matches_with_decisions, goal_id
        )

        # 11. Log business event
        get_business_logger().info(
            "goal_email_sent_manually",
            event_type="goal_email",
            goal_id=goal_id,
            user_id=user_id,
            items_count=len(email_items),
            decisions_updated=decisions_updated,
        )

        return SendEmailResult(
            success=True,
            email_sent=True,
            items_count=len(email_items),
            decisions_updated=decisions_updated,
            message="邮件发送成功",
        )

    async def _build_email_items(
        self,
        matches_with_decisions: list[tuple[GoalItemMatch, str | None]],
        goal_id: str,
    ) -> list[EmailItem]:
        """Build EmailItem list from matches."""
        email_items = []

        for match, _decision_id in matches_with_decisions:
            item = await self.item_repo.get_by_id(match.item_id)
            if not item:
                continue

            # Get source name
            source_name = None
            if item.source_id:
                source = await self.source_repo.get_by_id(item.source_id)
                if source:
                    source_name = source.name

            # Build redirect URL for click tracking
            redirect_url = build_redirect_url(
                base_url=settings.BACKEND_HOST,
                item_id=item.id,
                goal_id=goal_id,
                channel="email",
            )

            # Extract reason from match
            reason = "手动推送"
            if match.reasons_json and match.reasons_json.get("summary"):
                reason = match.reasons_json["summary"]
            elif match.features_json:
                score = match.match_score
                reason = f"匹配分数: {score:.2f}"

            email_items.append(
                EmailItem(
                    item_id=item.id,
                    title=item.title,
                    snippet=item.snippet,
                    url=item.url,
                    source_name=source_name,
                    published_at=item.published_at,
                    reason=reason,
                    redirect_url=redirect_url,
                )
            )

        return email_items

    async def _update_push_decisions(
        self,
        matches_with_decisions: list[tuple[GoalItemMatch, str | None]],
        goal_id: str,
    ) -> int:
        """Update or create push decisions for sent items.

        For items with existing decisions: update status to SENT
        For items without decisions: create new decision with SENT status
        """
        updated_count = 0
        now = datetime.now(UTC)

        for match, decision_id in matches_with_decisions:
            if decision_id:
                # Update existing decision
                await self.decision_repo.batch_update_status(
                    ids=[decision_id],
                    status=PushStatus.SENT,
                    sent_at=now,
                )
                updated_count += 1
            else:
                # Create new decision
                decision = PushDecisionRecord(
                    goal_id=goal_id,
                    item_id=match.item_id,
                    decision=PushDecision.IMMEDIATE,
                    status=PushStatus.SENT,
                    channel=PushChannel.EMAIL,
                    reason_json={
                        "manual_trigger": True,
                        "triggered_at": now.isoformat(),
                    },
                    decided_at=now,
                    sent_at=now,
                    dedupe_key=f"manual:{goal_id}:{match.item_id}:{int(now.timestamp())}",
                )
                await self.decision_repo.create(decision)
                updated_count += 1

        return updated_count
