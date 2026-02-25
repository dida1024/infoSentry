"""Push orchestration service.

Handles:
- Immediate coalescing (5-minute buffer, max 3 items)
- Batch window scheduling
- Digest compilation
- Email dispatching
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from loguru import logger

from src.core.config import settings
from src.core.domain.url_topic import build_topic_key
from src.core.infrastructure.logging import BusinessEvents
from src.core.infrastructure.redis.client import RedisClient
from src.core.infrastructure.redis.keys import RedisKeys
from src.modules.push.application.email_service import EmailService, get_email_service
from src.modules.push.application.email_templates import (
    EmailData,
    EmailItem,
    build_redirect_url,
    render_batch_email,
    render_digest_email,
    render_immediate_email,
    render_plain_text_fallback,
)
from src.modules.push.domain.entities import (
    PushDecisionRecord,
    PushStatus,
)


class PushService:
    """Push orchestration service."""

    @dataclass
    class _EmailPayload:
        decision_id: str
        topic_key: str
        score: float
        published_at: datetime | None
        email_item: EmailItem

    def __init__(
        self,
        decision_repository,
        goal_repository,
        item_repository,
        source_repository,
        user_repository,
        redis_client: RedisClient,
        email_service: EmailService | None = None,
    ):
        self.decision_repo = decision_repository
        self.goal_repo = goal_repository
        self.item_repo = item_repository
        self.source_repo = source_repository
        self.user_repo = user_repository
        self.redis = redis_client
        self.email_service = email_service or get_email_service()

    # ============================================
    # Immediate Coalescing
    # ============================================

    async def add_to_immediate_buffer(
        self,
        goal_id: str,
        decision_id: str,
    ) -> bool:
        """Add a decision to the immediate coalesce buffer.

        Args:
            goal_id: Goal ID
            decision_id: Decision ID

        Returns:
            True if added, False if buffer is full
        """
        # Calculate time bucket (5-minute windows)
        now = datetime.now(UTC)
        time_bucket = now.strftime("%Y%m%d%H") + str(now.minute // 5)

        buffer_key = RedisKeys.immediate_buffer(goal_id, time_bucket)

        # Check current size
        current_size = await self.redis.llen(buffer_key)
        if current_size >= settings.IMMEDIATE_MAX_ITEMS:
            logger.info(f"Immediate buffer full for goal {goal_id}")
            return False

        # Add to buffer
        await self.redis.rpush(buffer_key, decision_id)
        await self.redis.expire(buffer_key, 600)  # 10 minutes TTL

        logger.debug(f"Added decision {decision_id} to immediate buffer {buffer_key}")
        return True

    async def check_and_flush_immediate_buffers(self) -> list[str]:
        """Check all immediate buffers and flush ready ones.

        Buffers are ready when:
        - 5 minutes have passed since the first item
        - OR buffer has 3 items

        Returns:
            List of goal IDs that were flushed
        """
        flushed_goals = []

        # Scan for all immediate buffer keys
        pattern = RedisKeys.immediate_buffer_pattern()

        # Use scan instead of keys for production safety
        cursor = 0
        while True:
            cursor, keys = await self.redis.client.scan(
                cursor=cursor,
                match=pattern,
                count=100,
            )

            for key in keys:
                # Parse goal_id and time_bucket from key
                # Format: buffer:immediate:{goal_id}:{time_bucket}
                parts = key.split(":")
                if len(parts) >= 4:
                    goal_id = parts[2]
                    time_bucket = parts[3]

                    # Check if buffer should be flushed
                    if await self._should_flush_buffer(goal_id, time_bucket):
                        await self._flush_immediate_buffer(goal_id, time_bucket)
                        flushed_goals.append(goal_id)

            if cursor == 0:
                break

        return flushed_goals

    async def _should_flush_buffer(self, goal_id: str, time_bucket: str) -> bool:
        """Check if a buffer should be flushed.

        Flush when:
        - Current time is in a different 5-minute bucket
        - OR buffer has max items
        """
        now = datetime.now(UTC)
        current_bucket = now.strftime("%Y%m%d%H") + str(now.minute // 5)

        # Flush if we're in a different time bucket
        if current_bucket != time_bucket:
            return True

        # Flush if buffer is full
        buffer_key = RedisKeys.immediate_buffer(goal_id, time_bucket)
        size = await self.redis.llen(buffer_key)
        return size >= settings.IMMEDIATE_MAX_ITEMS

    async def _flush_immediate_buffer(
        self,
        goal_id: str,
        time_bucket: str,
    ) -> bool:
        """Flush an immediate buffer and send email.

        Args:
            goal_id: Goal ID
            time_bucket: Time bucket

        Returns:
            True if email sent successfully
        """
        buffer_key = RedisKeys.immediate_buffer(goal_id, time_bucket)

        # Get all decision IDs from buffer
        decision_ids = await self.redis.lrange(buffer_key, 0, -1)
        if not decision_ids:
            return False

        # Delete buffer first to prevent duplicate processing
        await self.redis.delete(buffer_key)

        logger.info(
            f"Flushing immediate buffer for goal {goal_id}, "
            f"bucket {time_bucket}, {len(decision_ids)} decisions"
        )

        # Send email
        success = await self._send_immediate_email(goal_id, decision_ids)

        if not success:
            logger.warning(
                f"Failed to send immediate email for goal {goal_id}, "
                f"decisions will remain in PENDING status"
            )

        return success

    async def _send_immediate_email(
        self,
        goal_id: str,
        decision_ids: list[str],
    ) -> bool:
        """Send immediate email for a goal.

        Args:
            goal_id: Goal ID
            decision_ids: List of decision IDs to include

        Returns:
            True if email sent successfully
        """
        # Get goal
        goal = await self.goal_repo.get_by_id(goal_id)
        if not goal:
            logger.error(f"Goal not found: {goal_id}")
            return False

        # Get user email
        user = await self.user_repo.get_by_id(goal.user_id)
        if not user:
            logger.error(f"User not found for goal: {goal_id}")
            return False

        # Fetch decisions
        decisions = []
        for decision_id in decision_ids:
            decision = await self.decision_repo.get_by_id(decision_id)
            if decision:
                decisions.append(decision)

        # Sort by match score (desc)
        decisions = self._sort_decisions_by_score(decisions)

        # Build email payloads
        email_payloads: list[PushService._EmailPayload] = []
        for decision in decisions:
            item = await self.item_repo.get_by_id(decision.item_id)
            if not item:
                continue

            source_name = None
            if item.source_id:
                source = await self.source_repo.get_by_id(item.source_id)
                source_name = source.name if source else None

            redirect_url = build_redirect_url(
                settings.BACKEND_HOST,
                item.id,
                goal_id,
                "email",
            )

            email_payloads.append(
                self._EmailPayload(
                    decision_id=decision.id,
                    topic_key=item.topic_key or build_topic_key(item.url),
                    score=self._extract_decision_score(decision),
                    published_at=item.published_at,
                    email_item=EmailItem(
                        item_id=item.id,
                        title=item.title,
                        snippet=item.snippet,
                        url=item.url,
                        source_name=source_name,
                        published_at=item.published_at,
                        reason=decision.reason_json.get("reason", "匹配您的目标"),
                        redirect_url=redirect_url,
                    ),
                )
            )

        kept_payloads, dropped_payloads = self._dedupe_email_payloads(email_payloads)
        email_items = [payload.email_item for payload in kept_payloads]
        deduped_decision_ids = [payload.decision_id for payload in kept_payloads]
        dropped_decision_ids = [payload.decision_id for payload in dropped_payloads]
        if dropped_decision_ids:
            await self.decision_repo.batch_update_status(
                ids=dropped_decision_ids,
                status=PushStatus.SKIPPED,
            )

        if not email_items:
            logger.warning(f"No valid items for immediate email, goal={goal_id}")
            return False

        # Build email data
        email_data = EmailData(
            to_email=user.email,
            goal_id=goal_id,
            goal_name=goal.name,
            items=email_items,
            decision_ids=deduped_decision_ids,
        )

        # Render email
        subject, html_body = render_immediate_email(email_data, settings.BACKEND_HOST)
        plain_body = render_plain_text_fallback(email_data)

        # Send email
        result = await self.email_service.send_email(
            to_email=user.email,
            subject=subject,
            html_body=html_body,
            plain_body=plain_body,
        )

        if result.success:
            # Update decision status
            await self.decision_repo.batch_update_status(
                ids=deduped_decision_ids,
                status=PushStatus.SENT,
                sent_at=datetime.now(UTC),
            )
            logger.info(f"Immediate email sent to {user.email} for goal {goal_id}")
            # 记录业务事件
            BusinessEvents.email_sent(
                goal_id=goal_id,
                to_email=user.email,
                email_type="immediate",
                success=True,
                item_count=len(email_items),
            )
        else:
            # Mark as failed
            await self.decision_repo.batch_update_status(
                ids=deduped_decision_ids,
                status=PushStatus.FAILED,
            )
            logger.error(f"Failed to send immediate email: {result.error}")
            # 记录业务事件
            BusinessEvents.email_sent(
                goal_id=goal_id,
                to_email=user.email,
                email_type="immediate",
                success=False,
                error=result.error,
            )

        return result.success

    # ============================================
    # Batch Processing
    # ============================================

    async def process_batch_window(
        self,
        goal_id: str,
        window_time: str,
    ) -> bool:
        """Process batch window for a goal.

        Args:
            goal_id: Goal ID
            window_time: Window time (HH:MM)

        Returns:
            True if email sent successfully
        """
        logger.info(f"Processing batch window for goal {goal_id} at {window_time}")

        # Get pending BATCH decisions
        window_start = datetime.now(UTC) - timedelta(hours=24)
        window_end = datetime.now(UTC)

        decisions = await self.decision_repo.list_pending_batch(
            goal_id=goal_id,
            window_start=window_start,
            window_end=window_end,
            limit=settings.BATCH_MAX_ITEMS,
        )

        if not decisions:
            logger.info(f"No pending batch decisions for goal {goal_id}")
            return True

        decisions = self._sort_decisions_by_score(decisions)

        # Get goal and user
        goal = await self.goal_repo.get_by_id(goal_id)
        if not goal:
            logger.error(f"Goal not found: {goal_id}")
            return False

        user = await self.user_repo.get_by_id(goal.user_id)
        if not user:
            logger.error(f"User not found for goal: {goal_id}")
            return False

        # Build email payloads
        email_payloads: list[PushService._EmailPayload] = []

        for decision in decisions:
            item = await self.item_repo.get_by_id(decision.item_id)
            if not item:
                continue

            source_name = None
            if item.source_id:
                source = await self.source_repo.get_by_id(item.source_id)
                source_name = source.name if source else None

            redirect_url = build_redirect_url(
                settings.BACKEND_HOST,
                item.id,
                goal_id,
                "email",
            )

            email_payloads.append(
                self._EmailPayload(
                    decision_id=decision.id,
                    topic_key=item.topic_key or build_topic_key(item.url),
                    score=self._extract_decision_score(decision),
                    published_at=item.published_at,
                    email_item=EmailItem(
                        item_id=item.id,
                        title=item.title,
                        snippet=item.snippet,
                        url=item.url,
                        source_name=source_name,
                        published_at=item.published_at,
                        reason=decision.reason_json.get("reason", "匹配您的目标"),
                        redirect_url=redirect_url,
                    ),
                )
            )

        kept_payloads, dropped_payloads = self._dedupe_email_payloads(email_payloads)
        email_items = [payload.email_item for payload in kept_payloads]
        decision_ids = [payload.decision_id for payload in kept_payloads]
        dropped_decision_ids = [payload.decision_id for payload in dropped_payloads]
        if dropped_decision_ids:
            await self.decision_repo.batch_update_status(
                ids=dropped_decision_ids,
                status=PushStatus.SKIPPED,
            )

        if not email_items:
            logger.info(f"No valid items for batch email, goal={goal_id}")
            return True

        # Build email data
        email_data = EmailData(
            to_email=user.email,
            goal_id=goal_id,
            goal_name=goal.name,
            items=email_items,
            decision_ids=decision_ids,
        )

        # Render email
        subject, html_body = render_batch_email(
            email_data, window_time, settings.BACKEND_HOST
        )
        plain_body = render_plain_text_fallback(email_data)

        # Send email
        result = await self.email_service.send_email(
            to_email=user.email,
            subject=subject,
            html_body=html_body,
            plain_body=plain_body,
        )

        if result.success:
            await self.decision_repo.batch_update_status(
                ids=decision_ids,
                status=PushStatus.SENT,
                sent_at=datetime.now(UTC),
            )
            logger.info(
                f"Batch email sent to {user.email} for goal {goal_id}, "
                f"{len(email_items)} items"
            )
        else:
            await self.decision_repo.batch_update_status(
                ids=decision_ids,
                status=PushStatus.FAILED,
            )
            logger.error(f"Failed to send batch email: {result.error}")

        return result.success

    # ============================================
    # Digest Processing
    # ============================================

    async def process_digest(self, goal_id: str) -> bool:
        """Process daily digest for a goal.

        Args:
            goal_id: Goal ID

        Returns:
            True if email sent successfully
        """
        logger.info(f"Processing digest for goal {goal_id}")

        # Get pending DIGEST decisions from last 24 hours
        since = datetime.now(UTC) - timedelta(hours=24)

        decisions = await self.decision_repo.list_pending_digest(
            goal_id=goal_id,
            since=since,
            limit=settings.DIGEST_MAX_ITEMS_PER_GOAL,
        )

        if not decisions:
            logger.info(f"No pending digest decisions for goal {goal_id}")
            return True

        decisions = self._sort_decisions_by_score(decisions)

        # Get goal and user
        goal = await self.goal_repo.get_by_id(goal_id)
        if not goal:
            logger.error(f"Goal not found: {goal_id}")
            return False

        user = await self.user_repo.get_by_id(goal.user_id)
        if not user:
            logger.error(f"User not found for goal: {goal_id}")
            return False

        # Build email payloads
        email_payloads: list[PushService._EmailPayload] = []

        for decision in decisions:
            item = await self.item_repo.get_by_id(decision.item_id)
            if not item:
                continue

            source_name = None
            if item.source_id:
                source = await self.source_repo.get_by_id(item.source_id)
                source_name = source.name if source else None

            redirect_url = build_redirect_url(
                settings.BACKEND_HOST,
                item.id,
                goal_id,
                "email",
            )

            email_payloads.append(
                self._EmailPayload(
                    decision_id=decision.id,
                    topic_key=item.topic_key or build_topic_key(item.url),
                    score=self._extract_decision_score(decision),
                    published_at=item.published_at,
                    email_item=EmailItem(
                        item_id=item.id,
                        title=item.title,
                        snippet=item.snippet,
                        url=item.url,
                        source_name=source_name,
                        published_at=item.published_at,
                        reason=decision.reason_json.get("reason", "匹配您的目标"),
                        redirect_url=redirect_url,
                    ),
                )
            )

        kept_payloads, dropped_payloads = self._dedupe_email_payloads(email_payloads)
        email_items = [payload.email_item for payload in kept_payloads]
        decision_ids = [payload.decision_id for payload in kept_payloads]
        dropped_decision_ids = [payload.decision_id for payload in dropped_payloads]
        if dropped_decision_ids:
            await self.decision_repo.batch_update_status(
                ids=dropped_decision_ids,
                status=PushStatus.SKIPPED,
            )

        if not email_items:
            logger.info(f"No valid items for digest email, goal={goal_id}")
            return True

        # Build email data
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        email_data = EmailData(
            to_email=user.email,
            goal_id=goal_id,
            goal_name=goal.name,
            items=email_items,
            decision_ids=decision_ids,
        )

        # Render email
        subject, html_body = render_digest_email(
            email_data, date_str, settings.BACKEND_HOST
        )
        plain_body = render_plain_text_fallback(email_data)

        # Send email
        result = await self.email_service.send_email(
            to_email=user.email,
            subject=subject,
            html_body=html_body,
            plain_body=plain_body,
        )

        if result.success:
            await self.decision_repo.batch_update_status(
                ids=decision_ids,
                status=PushStatus.SENT,
                sent_at=datetime.now(UTC),
            )
            logger.info(
                f"Digest email sent to {user.email} for goal {goal_id}, "
                f"{len(email_items)} items"
            )
        else:
            await self.decision_repo.batch_update_status(
                ids=decision_ids,
                status=PushStatus.FAILED,
            )
            logger.error(f"Failed to send digest email: {result.error}")

        return result.success

    def _sort_decisions_by_score(
        self, decisions: list[PushDecisionRecord]
    ) -> list[PushDecisionRecord]:
        """按匹配度排序决策（降序）。"""
        return sorted(
            decisions,
            key=lambda d: (self._extract_decision_score(d), d.decided_at),
            reverse=True,
        )

    def _extract_decision_score(self, decision: PushDecisionRecord) -> float:
        """从决策记录中提取匹配分数。"""
        reason_json = decision.reason_json or {}
        score_trace = reason_json.get("score_trace", {})
        adjusted = score_trace.get("adjusted_score")
        if isinstance(adjusted, (int, float)):
            return float(adjusted)
        match_score = reason_json.get("match_score")
        if isinstance(match_score, (int, float)):
            return float(match_score)
        return 0.0

    def _dedupe_email_payloads(
        self, payloads: list[_EmailPayload]
    ) -> tuple[list[_EmailPayload], list[_EmailPayload]]:
        """Deduplicate email payloads by topic key.

        Keep the item with higher score for the same topic.
        If score ties, keep the newer published_at.
        """
        kept_by_topic: dict[str, PushService._EmailPayload] = {}
        dropped: list[PushService._EmailPayload] = []

        for payload in payloads:
            existing = kept_by_topic.get(payload.topic_key)
            if not existing:
                kept_by_topic[payload.topic_key] = payload
                continue

            existing_pub = existing.published_at or datetime.min.replace(tzinfo=UTC)
            current_pub = payload.published_at or datetime.min.replace(tzinfo=UTC)
            keep_current = payload.score > existing.score or (
                payload.score == existing.score and current_pub > existing_pub
            )
            if keep_current:
                dropped.append(existing)
                kept_by_topic[payload.topic_key] = payload
            else:
                dropped.append(payload)

        kept = sorted(
            kept_by_topic.values(),
            key=lambda p: (p.score, p.published_at),
            reverse=True,
        )
        return kept, dropped
