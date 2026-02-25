"""Goal match ranking integration tests."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from src.core.domain.url_topic import build_topic_key
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
        topic_key=build_topic_key("https://example.com/old"),
        title="Old item",
        published_at=old_published,
        ingested_at=old_published,
    )
    item_new = ItemModel(
        id="item-new",
        source_id=source.id,
        url="https://example.com/new",
        url_hash="hash-new",
        topic_key=build_topic_key("https://example.com/new"),
        title="New item",
        published_at=new_published,
        ingested_at=new_published,
    )

    match_old = GoalItemMatchModel(
        id="match-old",
        goal_id=goal.id,
        item_id=item_old.id,
        topic_key=item_old.topic_key,
        item_time=old_published,
        match_score=0.95,
        features_json={},
        reasons_json={},
        computed_at=now,
    )
    match_new = GoalItemMatchModel(
        id="match-new",
        goal_id=goal.id,
        item_id=item_new.id,
        topic_key=item_new.topic_key,
        item_time=new_published,
        match_score=0.90,
        features_json={},
        reasons_json={},
        computed_at=now,
    )

    db_session.add_all([source, goal, item_old, item_new, match_old, match_new])
    await db_session.flush()
    return goal.id, item_old.id, item_new.id


async def _seed_topic_duplicates(db_session, now: datetime) -> str:
    source = SourceModel(
        id="source-dedup",
        type=SourceType.RSS,
        owner_id="user-dedup",
        name="Dedup Source",
        config={"feed_url": "https://example.com/feed.xml"},
    )
    goal = GoalModel(
        id="goal-dedup",
        user_id="user-dedup",
        name="Dedup Goal",
        description="Dedup goal for tests",
        status=GoalStatus.ACTIVE,
        priority_mode=PriorityMode.SOFT,
    )

    topic_same = build_topic_key("https://www.v2ex.com/t/100")
    topic_other = build_topic_key("https://www.v2ex.com/t/101")

    item_1 = ItemModel(
        id="item-dedup-1",
        source_id=source.id,
        url="https://www.v2ex.com/t/100#reply0",
        url_hash="hash-dedup-1",
        topic_key=topic_same,
        title="same-topic-1",
        published_at=now - timedelta(hours=2),
        ingested_at=now - timedelta(hours=2),
    )
    item_2 = ItemModel(
        id="item-dedup-2",
        source_id=source.id,
        url="https://www.v2ex.com/t/100#reply9",
        url_hash="hash-dedup-2",
        topic_key=topic_same,
        title="same-topic-2",
        published_at=now - timedelta(hours=1),
        ingested_at=now - timedelta(hours=1),
    )
    item_3 = ItemModel(
        id="item-dedup-3",
        source_id=source.id,
        url="https://www.v2ex.com/t/101#reply1",
        url_hash="hash-dedup-3",
        topic_key=topic_other,
        title="other-topic",
        published_at=now - timedelta(hours=3),
        ingested_at=now - timedelta(hours=3),
    )

    match_1 = GoalItemMatchModel(
        id="match-dedup-1",
        goal_id=goal.id,
        item_id=item_1.id,
        topic_key=topic_same,
        item_time=item_1.published_at,
        match_score=0.91,
        features_json={},
        reasons_json={},
        computed_at=now,
    )
    match_2 = GoalItemMatchModel(
        id="match-dedup-2",
        goal_id=goal.id,
        item_id=item_2.id,
        topic_key=topic_same,
        item_time=item_2.published_at,
        match_score=0.89,
        features_json={},
        reasons_json={},
        computed_at=now,
    )
    match_3 = GoalItemMatchModel(
        id="match-dedup-3",
        goal_id=goal.id,
        item_id=item_3.id,
        topic_key=topic_other,
        item_time=item_3.published_at,
        match_score=0.87,
        features_json={},
        reasons_json={},
        computed_at=now,
    )

    db_session.add_all(
        [source, goal, item_1, item_2, item_3, match_1, match_2, match_3]
    )
    await db_session.flush()
    return goal.id


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


async def test_list_by_goal_deduped_returns_one_per_topic(db_session) -> None:
    now = datetime.now(UTC)
    goal_id = await _seed_topic_duplicates(db_session, now)

    repo = PostgreSQLGoalItemMatchRepository(
        session=db_session,
        mapper=GoalItemMatchMapper(),
        event_publisher=EventBus(),
    )

    matches, total = await repo.list_by_goal_deduped(
        goal_id=goal_id,
        rank_mode=RankMode.MATCH_SCORE,
        page=1,
        page_size=10,
    )

    assert total == 2
    assert [match.item_id for match in matches] == ["item-dedup-1", "item-dedup-3"]
