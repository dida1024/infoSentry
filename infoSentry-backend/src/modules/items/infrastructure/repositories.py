"""Item repository implementations."""

from datetime import datetime

from loguru import logger
from sqlalchemy import func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.domain.events import EventBus
from src.core.infrastructure.database.event_aware_repository import EventAwareRepository
from src.modules.items.domain.entities import EmbeddingStatus, GoalItemMatch, Item
from src.modules.items.domain.repository import GoalItemMatchRepository, ItemRepository
from src.modules.items.infrastructure.mappers import GoalItemMatchMapper, ItemMapper
from src.modules.items.infrastructure.models import GoalItemMatchModel, ItemModel


class PostgreSQLItemRepository(EventAwareRepository[Item], ItemRepository):
    """PostgreSQL item repository implementation."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: ItemMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper
        self.logger = logger

    async def get_by_id(self, item_id: str) -> Item | None:
        statement = select(ItemModel).where(
            ItemModel.id == item_id,
            ItemModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_by_url_hash(self, url_hash: str) -> Item | None:
        statement = select(ItemModel).where(
            ItemModel.url_hash == url_hash,
            ItemModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def exists_by_url_hash(self, url_hash: str) -> bool:
        statement = select(ItemModel).where(
            ItemModel.url_hash == url_hash,
            ItemModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def list_by_source(
        self,
        source_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Item], int]:
        statement = (
            select(ItemModel, func.count(ItemModel.id).over().label("total_count"))
            .where(
                ItemModel.source_id == source_id,
                ItemModel.is_deleted.is_(False),
            )
            .order_by(ItemModel.published_at.desc().nullslast())
        )

        statement = statement.offset((page - 1) * page_size).limit(page_size)

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.ItemModel for row in rows]
        return self.mapper.to_domain_list(models), total_count

    async def list_pending_embedding(self, limit: int = 100) -> list[Item]:
        statement = (
            select(ItemModel)
            .where(
                ItemModel.embedding_status == EmbeddingStatus.PENDING,
                ItemModel.is_deleted.is_(False),
            )
            .order_by(ItemModel.ingested_at.asc())
            .limit(limit)
        )

        result = await self.session.execute(statement)
        models = result.scalars().all()
        return self.mapper.to_domain_list(list(models))

    async def list_recent(
        self,
        since: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Item], int]:
        statement = select(
            ItemModel, func.count(ItemModel.id).over().label("total_count")
        ).where(ItemModel.is_deleted.is_(False))

        if since:
            statement = statement.where(ItemModel.ingested_at >= since)

        statement = (
            statement.order_by(ItemModel.ingested_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.ItemModel for row in rows]
        return self.mapper.to_domain_list(models), total_count

    async def search_similar(
        self,
        embedding: list[float],
        limit: int = 20,
        min_score: float = 0.5,
    ) -> list[tuple[Item, float]]:
        # 使用 pgvector 的余弦相似度
        # 1 - cosine_distance = cosine_similarity
        statement = text("""
            SELECT *, 1 - (embedding <=> :embedding::vector) as similarity
            FROM items
            WHERE is_deleted = false
              AND embedding IS NOT NULL
              AND 1 - (embedding <=> :embedding::vector) >= :min_score
            ORDER BY embedding <=> :embedding::vector
            LIMIT :limit
        """)

        result = await self.session.execute(
            statement,
            {
                "embedding": str(embedding),
                "min_score": min_score,
                "limit": limit,
            },
        )
        rows = result.fetchall()

        items_with_scores = []
        for row in rows:
            # 将 row 转换为 ItemModel
            model = ItemModel(
                id=row.id,
                source_id=row.source_id,
                url=row.url,
                url_hash=row.url_hash,
                title=row.title,
                snippet=row.snippet,
                summary=row.summary,
                published_at=row.published_at,
                ingested_at=row.ingested_at,
                embedding=row.embedding,
                embedding_status=row.embedding_status,
                embedding_model=row.embedding_model,
                raw_data=row.raw_data,
                created_at=row.created_at,
                updated_at=row.updated_at,
                is_deleted=row.is_deleted,
            )
            item = self.mapper.to_domain(model)
            items_with_scores.append((item, row.similarity))

        return items_with_scores

    async def create(self, item: Item) -> Item:
        model = self.mapper.to_model(item)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        await self._publish_events_from_entity(item)
        return self.mapper.to_domain(model)

    async def update(self, item: Item) -> Item:
        statement = select(ItemModel).where(ItemModel.id == item.id)
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise ValueError(f"Item with id {item.id} not found")

        existing.title = item.title
        existing.snippet = item.snippet
        existing.summary = item.summary
        existing.embedding = item.embedding
        existing.embedding_status = item.embedding_status
        existing.embedding_model = item.embedding_model
        existing.raw_data = item.raw_data
        existing.updated_at = item.updated_at
        existing.is_deleted = item.is_deleted

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        await self._publish_events_from_entity(item)
        return self.mapper.to_domain(existing)

    async def delete(self, item: Item | str) -> bool:
        item_id = item.id if isinstance(item, Item) else item
        statement = select(ItemModel).where(
            ItemModel.id == item_id,
            ItemModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        if not model:
            return False

        model.is_deleted = True
        self.session.add(model)
        await self.session.flush()
        return True

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 10,
        include_deleted: bool = False,
    ) -> tuple[list[Item], int]:
        return await self.list_recent(page=page, page_size=page_size)


class PostgreSQLGoalItemMatchRepository(
    EventAwareRepository[GoalItemMatch], GoalItemMatchRepository
):
    """PostgreSQL goal-item match repository."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: GoalItemMatchMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper

    async def get_by_id(self, match_id: str) -> GoalItemMatch | None:
        statement = select(GoalItemMatchModel).where(
            GoalItemMatchModel.id == match_id,
            GoalItemMatchModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_by_goal_and_item(
        self, goal_id: str, item_id: str
    ) -> GoalItemMatch | None:
        statement = select(GoalItemMatchModel).where(
            GoalItemMatchModel.goal_id == goal_id,
            GoalItemMatchModel.item_id == item_id,
            GoalItemMatchModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_by_goal(
        self,
        goal_id: str,
        min_score: float | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[GoalItemMatch], int]:
        statement = select(
            GoalItemMatchModel,
            func.count(GoalItemMatchModel.id).over().label("total_count"),
        ).where(
            GoalItemMatchModel.goal_id == goal_id,
            GoalItemMatchModel.is_deleted.is_(False),
        )

        if min_score is not None:
            statement = statement.where(GoalItemMatchModel.match_score >= min_score)

        statement = (
            statement.order_by(
                GoalItemMatchModel.match_score.desc(),
                GoalItemMatchModel.computed_at.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.GoalItemMatchModel for row in rows]
        return self.mapper.to_domain_list(models), total_count

    async def list_by_item(self, item_id: str) -> list[GoalItemMatch]:
        statement = select(GoalItemMatchModel).where(
            GoalItemMatchModel.item_id == item_id,
            GoalItemMatchModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        models = result.scalars().all()
        return self.mapper.to_domain_list(list(models))

    async def upsert(self, match: GoalItemMatch) -> GoalItemMatch:
        existing = await self.get_by_goal_and_item(match.goal_id, match.item_id)
        if existing:
            existing.update_score(
                match.match_score,
                match.features_json,
                match.reasons_json,
            )
            return await self.update(existing)
        return await self.create(match)

    async def create(self, match: GoalItemMatch) -> GoalItemMatch:
        model = self.mapper.to_model(match)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        await self._publish_events_from_entity(match)
        return self.mapper.to_domain(model)

    async def update(self, match: GoalItemMatch) -> GoalItemMatch:
        statement = select(GoalItemMatchModel).where(GoalItemMatchModel.id == match.id)
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise ValueError(f"GoalItemMatch with id {match.id} not found")

        existing.match_score = match.match_score
        existing.features_json = match.features_json
        existing.reasons_json = match.reasons_json
        existing.computed_at = match.computed_at
        existing.updated_at = match.updated_at

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        await self._publish_events_from_entity(match)
        return self.mapper.to_domain(existing)

    async def delete(self, match: GoalItemMatch | str) -> bool:
        match_id = match.id if isinstance(match, GoalItemMatch) else match
        statement = select(GoalItemMatchModel).where(GoalItemMatchModel.id == match_id)
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        if not model:
            return False
        model.is_deleted = True
        self.session.add(model)
        await self.session.flush()
        return True

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 10,
        include_deleted: bool = False,
    ) -> tuple[list[GoalItemMatch], int]:
        return [], 0

    async def list_top_by_goal(
        self,
        goal_id: str,
        min_score: float,
        since: datetime | None = None,
        limit: int = 10,
    ) -> list[GoalItemMatch]:
        """List top matching items for a goal.

        Args:
            goal_id: Goal ID
            min_score: Minimum match score
            since: Only include matches computed since this time
            limit: Maximum number of results

        Returns:
            List of GoalItemMatch sorted by score descending
        """
        statement = select(GoalItemMatchModel).where(
            GoalItemMatchModel.goal_id == goal_id,
            GoalItemMatchModel.match_score >= min_score,
            GoalItemMatchModel.is_deleted.is_(False),
        )

        if since:
            statement = statement.where(GoalItemMatchModel.computed_at >= since)

        statement = statement.order_by(
            GoalItemMatchModel.match_score.desc(),
            GoalItemMatchModel.computed_at.desc(),
        ).limit(limit)

        result = await self.session.execute(statement)
        models = result.scalars().all()
        return self.mapper.to_domain_list(list(models))
