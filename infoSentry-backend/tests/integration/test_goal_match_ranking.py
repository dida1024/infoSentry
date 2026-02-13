"""Goal match ranking integration tests."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from src.core.domain.events import EventBus
from src.modules.goals.domain.entities import GoalStatus, PriorityMode
from src.modules.goals.infrastructure.models import GoalModel
from src.modules.items.domain.entities import RankMode
from src.modules.items.infrastructure.mappers import GoalItemMatchMapper
from src.modules.items.infrastructure.models import GoalItemMatchModel, ItemModel
from src.modules.items.infrastructure.repositories import (
    PostgreSQLGoalItemMatchRepository,
)
from src.modules.sources.domain.entities import SourceType
from src.modules.sources.infrastructure.models import SourceModel

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.fixture(scope="module")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        "postgresql+psycopg://postgres:postgres@localhost:5432/infosentry_test",
        echo=False,
        pool_pre_ping=True,
    )

    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    except OperationalError:
        await engine.dispose()
        pytest.skip("Postgres 测试库不可用（infosentry_test）")

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()


async def _seed_matches(db_session, now: datetime) -> tuple[str, str, str]:
    source = SourceModel(
        id="source-ranking",
        type=SourceType.RSS,
        owner_id="user-ranking",
        name="Ranking Source",
        config={"feed_url": "https://example.com/feed.xml"},
    )
    goal = GoalModel(
        id="goal-ranking",
        user_id="user-ranking",
        name="Ranking Goal",
        description="Ranking goal for tests",
        status=GoalStatus.ACTIVE,
        priority_mode=PriorityMode.SOFT,
    )

    old_published = now - timedelta(days=30)
    new_published = now - timedelta(days=1)

    item_old = ItemModel(
        id="item-old",
        source_id=source.id,
        url="https://example.com/old",
        url_hash="hash-old",
        title="Old item",
        published_at=old_published,
        ingested_at=old_published,
    )
    item_new = ItemModel(
        id="item-new",
        source_id=source.id,
        url="https://example.com/new",
        url_hash="hash-new",
        title="New item",
        published_at=new_published,
        ingested_at=new_published,
    )

    match_old = GoalItemMatchModel(
        id="match-old",
        goal_id=goal.id,
        item_id=item_old.id,
        match_score=0.95,
        features_json={},
        reasons_json={},
        computed_at=now,
    )
    match_new = GoalItemMatchModel(
        id="match-new",
        goal_id=goal.id,
        item_id=item_new.id,
        match_score=0.90,
        features_json={},
        reasons_json={},
        computed_at=now,
    )

    db_session.add_all([source, goal, item_old, item_new, match_old, match_new])
    await db_session.flush()
    return goal.id, item_old.id, item_new.id


async def test_list_by_goal_hybrid_ranks_recent_first(db_session) -> None:
    now = datetime.now(UTC)
    goal_id, item_old_id, item_new_id = await _seed_matches(db_session, now)

    repo = PostgreSQLGoalItemMatchRepository(
        session=db_session,
        mapper=GoalItemMatchMapper(),
        event_publisher=EventBus(),
    )

    matches, total = await repo.list_by_goal(
        goal_id=goal_id,
        rank_mode=RankMode.HYBRID,
        half_life_days=14,
    )

    assert total == 2
    assert [match.item_id for match in matches[:2]] == [item_new_id, item_old_id]


async def test_list_by_goal_match_score_keeps_score_order(db_session) -> None:
    now = datetime.now(UTC)
    goal_id, item_old_id, item_new_id = await _seed_matches(db_session, now)

    repo = PostgreSQLGoalItemMatchRepository(
        session=db_session,
        mapper=GoalItemMatchMapper(),
        event_publisher=EventBus(),
    )

    matches, total = await repo.list_by_goal(
        goal_id=goal_id,
        rank_mode=RankMode.MATCH_SCORE,
        half_life_days=14,
    )

    assert total == 2
    assert [match.item_id for match in matches[:2]] == [item_old_id, item_new_id]


async def test_list_by_goal_recent_orders_by_item_time(db_session) -> None:
    now = datetime.now(UTC)
    goal_id, item_old_id, item_new_id = await _seed_matches(db_session, now)

    repo = PostgreSQLGoalItemMatchRepository(
        session=db_session,
        mapper=GoalItemMatchMapper(),
        event_publisher=EventBus(),
    )

    matches, total = await repo.list_by_goal(
        goal_id=goal_id,
        rank_mode=RankMode.RECENT,
    )

    assert total == 2
    assert [match.item_id for match in matches[:2]] == [item_new_id, item_old_id]
