"""Push PostgreSQL repository implementations."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from src.core.domain.events import EventBus
from src.modules.push.domain.entities import (
    BlockedSource,
    ClickEvent,
    ItemFeedback,
    PushDecision,
    PushDecisionRecord,
    PushStatus,
)
from src.modules.push.domain.repository import (
    BlockedSourceRepository,
    ClickEventRepository,
    ItemFeedbackRepository,
    PushDecisionRepository,
)
from src.modules.push.infrastructure.mappers import (
    BlockedSourceMapper,
    ClickEventMapper,
    ItemFeedbackMapper,
    PushDecisionMapper,
)
from src.modules.push.infrastructure.models import (
    BlockedSourceModel,
    ClickEventModel,
    ItemFeedbackModel,
    PushDecisionModel,
)


class PostgreSQLPushDecisionRepository(PushDecisionRepository):
    """PostgreSQL implementation of PushDecisionRepository."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: PushDecisionMapper,
        event_bus: EventBus,
    ):
        self.session = session
        self.mapper = mapper
        self.event_bus = event_bus

    async def get_by_id(self, id: str) -> PushDecisionRecord | None:
        """Get decision by ID."""
        result = await self.session.get(PushDecisionModel, id)
        return self.mapper.to_entity(result) if result else None

    async def create(self, entity: PushDecisionRecord) -> PushDecisionRecord:
        """Create a new decision."""
        model = self.mapper.to_model(entity)
        self.session.add(model)
        await self.session.flush()
        return self.mapper.to_entity(model)

    async def update(self, entity: PushDecisionRecord) -> PushDecisionRecord:
        """Update an existing decision."""
        model = self.mapper.to_model(entity)
        merged = await self.session.merge(model)
        await self.session.flush()
        return self.mapper.to_entity(merged)

    async def delete(self, id: str) -> bool:
        """Delete a decision."""
        result = await self.session.get(PushDecisionModel, id)
        if result:
            await self.session.delete(result)
            await self.session.flush()
            return True
        return False

    async def list_all(
        self, page: int = 1, page_size: int = 10, include_deleted: bool = False
    ) -> tuple[list[PushDecisionRecord], int]:
        """List all decisions with pagination."""
        # Count query
        count_stmt = select(func.count(PushDecisionModel.id))
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Data query
        stmt = (
            select(PushDecisionModel)
            .order_by(PushDecisionModel.decided_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self.mapper.to_entity(m) for m in models], total

    async def get_by_dedupe_key(self, dedupe_key: str) -> PushDecisionRecord | None:
        """Get by dedupe key."""
        stmt = select(PushDecisionModel).where(
            PushDecisionModel.dedupe_key == dedupe_key
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self.mapper.to_entity(model) if model else None

    async def list_by_goal(
        self,
        goal_id: str,
        status: PushStatus | None = None,
        decision: PushDecision | None = None,
        page: int = 1,
        page_size: int = 50,
        since: datetime | None = None,
    ) -> tuple[list[PushDecisionRecord], int]:
        """List decisions by goal."""
        conditions = [PushDecisionModel.goal_id == goal_id]

        if status:
            conditions.append(PushDecisionModel.status == status)
        if decision:
            conditions.append(PushDecisionModel.decision == decision)
        if since:
            conditions.append(PushDecisionModel.decided_at >= since)

        # Count query
        count_stmt = select(func.count(PushDecisionModel.id)).where(and_(*conditions))
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Data query
        stmt = (
            select(PushDecisionModel)
            .where(and_(*conditions))
            .order_by(PushDecisionModel.decided_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self.mapper.to_entity(m) for m in models], total

    async def list_by_goal_and_item_ids(
        self,
        goal_id: str,
        item_ids: list[str],
    ) -> list[PushDecisionRecord]:
        """List decisions by goal and item IDs."""
        if not item_ids:
            return []

        stmt = (
            select(PushDecisionModel)
            .where(
                and_(
                    PushDecisionModel.goal_id == goal_id,
                    PushDecisionModel.item_id.in_(item_ids),
                )
            )
            .order_by(PushDecisionModel.decided_at.desc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self.mapper.to_entity(m) for m in models]

    async def list_pending_batch(
        self,
        goal_id: str,
        window_start: datetime,
        window_end: datetime,
        limit: int = 10,
    ) -> list[PushDecisionRecord]:
        """List pending batch decisions in a time window."""
        stmt = (
            select(PushDecisionModel)
            .where(
                and_(
                    PushDecisionModel.goal_id == goal_id,
                    PushDecisionModel.decision == PushDecision.BATCH,
                    PushDecisionModel.status == PushStatus.PENDING,
                    PushDecisionModel.decided_at >= window_start,
                    PushDecisionModel.decided_at <= window_end,
                )
            )
            .order_by(PushDecisionModel.decided_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self.mapper.to_entity(m) for m in models]

    async def list_pending_digest(
        self,
        goal_id: str,
        since: datetime,
        limit: int = 20,
    ) -> list[PushDecisionRecord]:
        """List items for digest that haven't been sent."""
        stmt = (
            select(PushDecisionModel)
            .where(
                and_(
                    PushDecisionModel.goal_id == goal_id,
                    PushDecisionModel.decision == PushDecision.DIGEST,
                    PushDecisionModel.status == PushStatus.PENDING,
                    PushDecisionModel.decided_at >= since,
                )
            )
            .order_by(PushDecisionModel.decided_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self.mapper.to_entity(m) for m in models]

    async def list_pending_immediate(
        self,
        goal_id: str,
        limit: int = 10,
    ) -> list[PushDecisionRecord]:
        """List pending immediate decisions."""
        stmt = (
            select(PushDecisionModel)
            .where(
                and_(
                    PushDecisionModel.goal_id == goal_id,
                    PushDecisionModel.decision == PushDecision.IMMEDIATE,
                    PushDecisionModel.status == PushStatus.PENDING,
                )
            )
            .order_by(PushDecisionModel.decided_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self.mapper.to_entity(m) for m in models]

    async def list_by_goals(
        self,
        goal_ids: list[str],
        status: PushStatus | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[PushDecisionRecord], int]:
        """List decisions for multiple goals."""
        if not goal_ids:
            return [], 0

        conditions = [PushDecisionModel.goal_id.in_(goal_ids)]

        if status:
            conditions.append(PushDecisionModel.status == status)

        # Count query
        count_stmt = select(func.count(PushDecisionModel.id)).where(and_(*conditions))
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Data query
        stmt = (
            select(PushDecisionModel)
            .where(and_(*conditions))
            .order_by(PushDecisionModel.decided_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self.mapper.to_entity(m) for m in models], total

    async def batch_update_status(
        self,
        ids: list[str],
        status: PushStatus,
        sent_at: datetime | None = None,
    ) -> int:
        """Batch update decision status."""
        from sqlalchemy import update

        values: dict[str, Any] = {"status": status, "updated_at": datetime.now(UTC)}
        if sent_at:
            values["sent_at"] = sent_at

        stmt = (
            update(PushDecisionModel)
            .where(PushDecisionModel.id.in_(ids))
            .values(**values)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount


class PostgreSQLClickEventRepository(ClickEventRepository):
    """PostgreSQL implementation of ClickEventRepository."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: ClickEventMapper,
        event_bus: EventBus,
    ):
        self.session = session
        self.mapper = mapper
        self.event_bus = event_bus

    async def get_by_id(self, id: str) -> ClickEvent | None:
        """Get click event by ID."""
        result = await self.session.get(ClickEventModel, id)
        return self.mapper.to_entity(result) if result else None

    async def create(self, entity: ClickEvent) -> ClickEvent:
        """Create a new click event."""
        model = self.mapper.to_model(entity)
        self.session.add(model)
        await self.session.flush()
        return self.mapper.to_entity(model)

    async def update(self, entity: ClickEvent) -> ClickEvent:
        """Update an existing click event."""
        model = self.mapper.to_model(entity)
        merged = await self.session.merge(model)
        await self.session.flush()
        return self.mapper.to_entity(merged)

    async def delete(self, id: str) -> bool:
        """Delete a click event."""
        result = await self.session.get(ClickEventModel, id)
        if result:
            await self.session.delete(result)
            await self.session.flush()
            return True
        return False

    async def list_all(
        self, page: int = 1, page_size: int = 10, include_deleted: bool = False
    ) -> tuple[list[ClickEvent], int]:
        """List all click events with pagination."""
        count_stmt = select(func.count(ClickEventModel.id))
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = (
            select(ClickEventModel)
            .order_by(ClickEventModel.clicked_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self.mapper.to_entity(m) for m in models], total

    async def list_by_item(self, item_id: str) -> list[ClickEvent]:
        """List clicks for an item."""
        stmt = (
            select(ClickEventModel)
            .where(ClickEventModel.item_id == item_id)
            .order_by(ClickEventModel.clicked_at.desc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self.mapper.to_entity(m) for m in models]

    async def count_by_goal(
        self,
        goal_id: str,
        since: datetime | None = None,
    ) -> int:
        """Count clicks for a goal."""
        conditions = [ClickEventModel.goal_id == goal_id]
        if since:
            conditions.append(ClickEventModel.clicked_at >= since)

        stmt = select(func.count(ClickEventModel.id)).where(and_(*conditions))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def list_by_goal(
        self,
        goal_id: str,
        limit: int = 10,
    ) -> list[ClickEvent]:
        """List clicks for a goal."""
        stmt = (
            select(ClickEventModel)
            .where(ClickEventModel.goal_id == goal_id)
            .order_by(ClickEventModel.clicked_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self.mapper.to_entity(m) for m in models]


class PostgreSQLItemFeedbackRepository(ItemFeedbackRepository):
    """PostgreSQL implementation of ItemFeedbackRepository."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: ItemFeedbackMapper,
        event_bus: EventBus,
    ):
        self.session = session
        self.mapper = mapper
        self.event_bus = event_bus

    async def get_by_id(self, id: str) -> ItemFeedback | None:
        """Get feedback by ID."""
        result = await self.session.get(ItemFeedbackModel, id)
        return self.mapper.to_entity(result) if result else None

    async def create(self, entity: ItemFeedback) -> ItemFeedback:
        """Create a new feedback."""
        model = self.mapper.to_model(entity)
        self.session.add(model)
        await self.session.flush()
        return self.mapper.to_entity(model)

    async def update(self, entity: ItemFeedback) -> ItemFeedback:
        """Update an existing feedback."""
        model = self.mapper.to_model(entity)
        merged = await self.session.merge(model)
        await self.session.flush()
        return self.mapper.to_entity(merged)

    async def delete(self, id: str) -> bool:
        """Delete a feedback."""
        result = await self.session.get(ItemFeedbackModel, id)
        if result:
            await self.session.delete(result)
            await self.session.flush()
            return True
        return False

    async def list_all(
        self, page: int = 1, page_size: int = 10, include_deleted: bool = False
    ) -> tuple[list[ItemFeedback], int]:
        """List all feedback with pagination."""
        count_stmt = select(func.count(ItemFeedbackModel.id))
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = (
            select(ItemFeedbackModel)
            .order_by(ItemFeedbackModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self.mapper.to_entity(m) for m in models], total

    async def get_by_item_goal_user(
        self,
        item_id: str,
        goal_id: str,
        user_id: str,
    ) -> ItemFeedback | None:
        """Get feedback for specific item/goal/user combination."""
        stmt = select(ItemFeedbackModel).where(
            and_(
                ItemFeedbackModel.item_id == item_id,
                ItemFeedbackModel.goal_id == goal_id,
                ItemFeedbackModel.user_id == user_id,
            )
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self.mapper.to_entity(model) if model else None

    async def list_by_goal(
        self,
        goal_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ItemFeedback], int]:
        """List feedback for a goal."""
        # Count
        count_stmt = select(func.count(ItemFeedbackModel.id)).where(
            ItemFeedbackModel.goal_id == goal_id
        )
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Data
        stmt = (
            select(ItemFeedbackModel)
            .where(ItemFeedbackModel.goal_id == goal_id)
            .order_by(ItemFeedbackModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self.mapper.to_entity(m) for m in models], total

    async def get_stats_by_goal(self, goal_id: str) -> dict[str, int]:
        """Get feedback statistics for a goal."""
        from src.modules.push.domain.entities import FeedbackType

        # Count likes
        like_stmt = select(func.count(ItemFeedbackModel.id)).where(
            and_(
                ItemFeedbackModel.goal_id == goal_id,
                ItemFeedbackModel.feedback == FeedbackType.LIKE,
            )
        )
        like_result = await self.session.execute(like_stmt)
        likes = like_result.scalar() or 0

        # Count dislikes
        dislike_stmt = select(func.count(ItemFeedbackModel.id)).where(
            and_(
                ItemFeedbackModel.goal_id == goal_id,
                ItemFeedbackModel.feedback == FeedbackType.DISLIKE,
            )
        )
        dislike_result = await self.session.execute(dislike_stmt)
        dislikes = dislike_result.scalar() or 0

        return {"like": likes, "dislike": dislikes}


class PostgreSQLBlockedSourceRepository(BlockedSourceRepository):
    """PostgreSQL implementation of BlockedSourceRepository."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: BlockedSourceMapper,
        event_bus: EventBus,
    ):
        self.session = session
        self.mapper = mapper
        self.event_bus = event_bus

    async def get_by_id(self, id: str) -> BlockedSource | None:
        """Get blocked source by ID."""
        result = await self.session.get(BlockedSourceModel, id)
        return self.mapper.to_entity(result) if result else None

    async def create(self, entity: BlockedSource) -> BlockedSource:
        """Create a new blocked source."""
        model = self.mapper.to_model(entity)
        self.session.add(model)
        await self.session.flush()
        return self.mapper.to_entity(model)

    async def update(self, entity: BlockedSource) -> BlockedSource:
        """Update an existing blocked source."""
        model = self.mapper.to_model(entity)
        merged = await self.session.merge(model)
        await self.session.flush()
        return self.mapper.to_entity(merged)

    async def delete(self, id: str) -> bool:
        """Delete a blocked source."""
        result = await self.session.get(BlockedSourceModel, id)
        if result:
            await self.session.delete(result)
            await self.session.flush()
            return True
        return False

    async def list_all(
        self, page: int = 1, page_size: int = 10, include_deleted: bool = False
    ) -> tuple[list[BlockedSource], int]:
        """List all blocked sources with pagination."""
        count_stmt = select(func.count(BlockedSourceModel.id))
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = (
            select(BlockedSourceModel)
            .order_by(BlockedSourceModel.blocked_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self.mapper.to_entity(m) for m in models], total

    async def is_blocked(
        self,
        user_id: str,
        source_id: str,
        goal_id: str | None = None,
    ) -> bool:
        """Check if source is blocked."""
        conditions = [
            BlockedSourceModel.user_id == user_id,
            BlockedSourceModel.source_id == source_id,
        ]

        if goal_id:
            # Check for specific goal or global block
            conditions.append(
                or_(
                    BlockedSourceModel.goal_id == goal_id,
                    col(BlockedSourceModel.goal_id).is_(None),
                )
            )

        stmt = select(func.count(BlockedSourceModel.id)).where(and_(*conditions))
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def list_by_user(
        self,
        user_id: str,
        goal_id: str | None = None,
    ) -> list[BlockedSource]:
        """List blocked sources for user."""
        conditions = [BlockedSourceModel.user_id == user_id]

        if goal_id:
            conditions.append(
                or_(
                    BlockedSourceModel.goal_id == goal_id,
                    col(BlockedSourceModel.goal_id).is_(None),
                )
            )

        stmt = (
            select(BlockedSourceModel)
            .where(and_(*conditions))
            .order_by(BlockedSourceModel.blocked_at.desc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self.mapper.to_entity(m) for m in models]

    async def list_by_goal(self, goal_id: str) -> list[BlockedSource]:
        """List blocked sources for a specific goal."""
        stmt = (
            select(BlockedSourceModel)
            .where(BlockedSourceModel.goal_id == goal_id)
            .order_by(BlockedSourceModel.blocked_at.desc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self.mapper.to_entity(m) for m in models]
