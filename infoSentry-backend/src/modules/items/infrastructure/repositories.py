"""Item repository implementations."""

from datetime import datetime
from typing import Any, cast

from loguru import logger
from sqlalchemy import func, literal, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import col, select

from src.core.config import settings
from src.core.domain.events import EventBus
from src.core.domain.exceptions import EntityNotFoundError
from src.core.infrastructure.database.event_aware_repository import EventAwareRepository
from src.modules.items.domain.entities import (
    EmbeddingStatus,
    GoalItemMatch,
    Item,
    RankMode,
)
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
            col(ItemModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_by_ids(self, item_ids: list[str]) -> dict[str, Item]:
        """Get items by IDs (batch query)."""
        if not item_ids:
            return {}

        statement = select(ItemModel).where(
            ItemModel.id.in_(item_ids),
            col(ItemModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        models = result.scalars().all()
        return {model.id: self.mapper.to_domain(model) for model in models}

    async def get_by_url_hash(self, url_hash: str) -> Item | None:
        statement = select(ItemModel).where(
            ItemModel.url_hash == url_hash,
            col(ItemModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def exists_by_url_hash(self, url_hash: str) -> bool:
        statement = select(ItemModel).where(
            ItemModel.url_hash == url_hash,
            col(ItemModel.is_deleted).is_(False),
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
                col(ItemModel.is_deleted).is_(False),
            )
            .order_by(col(ItemModel.published_at).desc().nullslast())
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
                col(ItemModel.is_deleted).is_(False),
            )
            .order_by(col(ItemModel.ingested_at).asc())
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
        ).where(col(ItemModel.is_deleted).is_(False))

        if since:
            statement = statement.where(ItemModel.ingested_at >= since)

        statement = (
            statement.order_by(col(ItemModel.ingested_at).desc())
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
                topic_key=row.topic_key,
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

    async def create_if_not_exists(self, item: Item) -> Item | None:
        """Create item if url_hash doesn't exist.

        使用 PostgreSQL INSERT ... ON CONFLICT DO NOTHING 实现原子操作。

        Args:
            item: 要创建的 Item 实体

        Returns:
            成功创建返回 Item，如果已存在返回 None
        """
        model = self.mapper.to_model(item)

        # 构建 INSERT ... ON CONFLICT DO NOTHING 语句
        stmt = (
            pg_insert(ItemModel)
            .values(
                id=model.id,
                created_at=model.created_at,
                updated_at=model.updated_at,
                is_deleted=model.is_deleted,
                source_id=model.source_id,
                url=model.url,
                url_hash=model.url_hash,
                topic_key=model.topic_key,
                title=model.title,
                snippet=model.snippet,
                summary=model.summary,
                published_at=model.published_at,
                ingested_at=model.ingested_at,
                embedding=model.embedding,
                embedding_status=model.embedding_status,
                embedding_model=model.embedding_model,
                raw_data=model.raw_data,
            )
            .on_conflict_do_nothing(
                index_elements=["url_hash"],
            )
            .returning(ItemModel)
        )

        result = await self.session.execute(stmt)
        inserted_row = result.scalar_one_or_none()

        if inserted_row is None:
            # 冲突，记录已存在
            return None

        await self._publish_events_from_entity(item)
        return self.mapper.to_domain(inserted_row)

    async def update(self, item: Item) -> Item:
        statement = select(ItemModel).where(ItemModel.id == item.id)
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise EntityNotFoundError("Item", item.id)

        existing.title = item.title
        existing.snippet = item.snippet
        existing.summary = item.summary
        existing.topic_key = item.topic_key
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
            col(ItemModel.is_deleted).is_(False),
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
            col(GoalItemMatchModel.is_deleted).is_(False),
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
            col(GoalItemMatchModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_by_goal(
        self,
        goal_id: str,
        min_score: float | None = None,
        since: datetime | None = None,
        rank_mode: RankMode = RankMode.HYBRID,
        half_life_days: float | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[GoalItemMatch], int]:
        statement = select(
            GoalItemMatchModel,
            func.count(GoalItemMatchModel.id).over().label("total_count"),
        ).where(
            GoalItemMatchModel.goal_id == goal_id,
            col(GoalItemMatchModel.is_deleted).is_(False),
        )

        if min_score is not None:
            statement = statement.where(GoalItemMatchModel.match_score >= min_score)
        if since:
            statement = statement.where(GoalItemMatchModel.computed_at >= since)

        effective_half_life = (
            half_life_days
            if half_life_days is not None and half_life_days > 0
            else settings.GOAL_MATCH_RANK_HALF_LIFE_DAYS
        )

        if rank_mode in {RankMode.HYBRID, RankMode.RECENT}:
            statement = statement.join(
                ItemModel, ItemModel.id == GoalItemMatchModel.item_id, isouter=True
            )
            item_time = cast(
                ColumnElement[datetime],
                func.coalesce(ItemModel.published_at, ItemModel.ingested_at),
            )

            if rank_mode == RankMode.HYBRID:
                age_seconds = func.extract("epoch", func.now() - item_time)
                age_days = func.greatest(age_seconds / 86400.0, 0.0)
                rank_score = cast(
                    ColumnElement[float],
                    GoalItemMatchModel.match_score
                    * func.power(0.5, age_days / effective_half_life),
                )
                statement = statement.order_by(
                    rank_score.desc().nullslast(),
                    col(GoalItemMatchModel.match_score).desc(),
                    col(GoalItemMatchModel.computed_at).desc(),
                )
            else:
                statement = statement.order_by(
                    item_time.desc().nullslast(),
                    col(GoalItemMatchModel.match_score).desc(),
                    col(GoalItemMatchModel.computed_at).desc(),
                )
        else:
            statement = statement.order_by(
                col(GoalItemMatchModel.match_score).desc(),
                col(GoalItemMatchModel.computed_at).desc(),
            )

        statement = statement.offset((page - 1) * page_size).limit(page_size)

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.GoalItemMatchModel for row in rows]
        return self.mapper.to_domain_list(models), total_count

    async def list_by_goal_deduped(
        self,
        goal_id: str,
        min_score: float | None = None,
        since: datetime | None = None,
        rank_mode: RankMode = RankMode.HYBRID,
        half_life_days: float | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[GoalItemMatch], int]:
        effective_half_life = (
            half_life_days
            if half_life_days is not None and half_life_days > 0
            else settings.GOAL_MATCH_RANK_HALF_LIFE_DAYS
        )

        base_filters = [
            col(GoalItemMatchModel.goal_id) == goal_id,
            col(GoalItemMatchModel.is_deleted).is_(False),
        ]
        if min_score is not None:
            base_filters.append(col(GoalItemMatchModel.match_score) >= min_score)
        if since:
            base_filters.append(col(GoalItemMatchModel.computed_at) >= since)

        item_time = cast(
            ColumnElement[datetime],
            func.coalesce(GoalItemMatchModel.item_time, GoalItemMatchModel.computed_at),
        )
        order_by = self._build_rank_order_by(
            rank_mode=rank_mode,
            item_time=item_time,
            half_life_days=effective_half_life,
        )
        topic_partition = cast(
            ColumnElement[str],
            func.coalesce(
                GoalItemMatchModel.topic_key,
                func.concat(literal("item:"), GoalItemMatchModel.item_id),
            ),
        )

        ranked_matches = (
            select(
                col(GoalItemMatchModel.id).label("match_id"),
                func.row_number()
                .over(partition_by=topic_partition, order_by=order_by)
                .label("rn"),
            )
            .where(*base_filters)
            .subquery("ranked_goal_matches")
        )
        deduped_ids = (
            select(ranked_matches.c.match_id)
            .where(ranked_matches.c.rn == 1)
            .subquery("deduped_goal_match_ids")
        )

        count_statement = select(func.count()).select_from(deduped_ids)
        count_result = await self.session.execute(count_statement)
        total_count = int(count_result.scalar_one() or 0)
        if total_count == 0:
            return [], 0

        statement = (
            select(GoalItemMatchModel)
            .join(deduped_ids, deduped_ids.c.match_id == col(GoalItemMatchModel.id))
            .order_by(*order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(statement)
        models = result.scalars().all()
        return self.mapper.to_domain_list(list(models)), total_count

    async def list_by_item(self, item_id: str) -> list[GoalItemMatch]:
        statement = select(GoalItemMatchModel).where(
            GoalItemMatchModel.item_id == item_id,
            col(GoalItemMatchModel.is_deleted).is_(False),
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
            existing.topic_key = match.topic_key
            existing.item_time = match.item_time
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
            raise EntityNotFoundError("GoalItemMatch", match.id)

        existing.match_score = match.match_score
        existing.topic_key = match.topic_key
        existing.item_time = match.item_time
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

    def _build_rank_order_by(
        self,
        rank_mode: RankMode,
        item_time: ColumnElement[datetime],
        half_life_days: float,
    ) -> list[ColumnElement[Any]]:
        if rank_mode == RankMode.HYBRID:
            age_seconds = func.extract("epoch", func.now() - item_time)
            age_days = func.greatest(age_seconds / 86400.0, 0.0)
            rank_score = cast(
                ColumnElement[float],
                GoalItemMatchModel.match_score
                * func.power(0.5, age_days / half_life_days),
            )
            return [
                rank_score.desc().nullslast(),
                col(GoalItemMatchModel.match_score).desc(),
                col(GoalItemMatchModel.computed_at).desc(),
            ]

        if rank_mode == RankMode.RECENT:
            return [
                item_time.desc().nullslast(),
                col(GoalItemMatchModel.match_score).desc(),
                col(GoalItemMatchModel.computed_at).desc(),
            ]

        return [
            col(GoalItemMatchModel.match_score).desc(),
            col(GoalItemMatchModel.computed_at).desc(),
        ]

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
            col(GoalItemMatchModel.is_deleted).is_(False),
        )

        if since:
            statement = statement.where(GoalItemMatchModel.computed_at >= since)

        statement = statement.order_by(
            col(GoalItemMatchModel.match_score).desc(),
            col(GoalItemMatchModel.computed_at).desc(),
        ).limit(limit)

        result = await self.session.execute(statement)
        models = result.scalars().all()
        return self.mapper.to_domain_list(list(models))
