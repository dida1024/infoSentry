"""GoalMatchQueryService 去重测试。"""

from datetime import UTC, datetime

import pytest

from src.modules.goals.application.services import GoalMatchQueryService
from src.modules.goals.domain.entities import Goal, GoalStatus, PriorityMode
from src.modules.items.domain.entities import (
    EmbeddingStatus,
    GoalItemMatch,
    Item,
    RankMode,
)
from src.modules.sources.domain.entities import Source, SourceType

pytestmark = pytest.mark.anyio


class _FakeGoalRepo:
    def __init__(self, goal: Goal | None) -> None:
        self._goal = goal

    async def get_by_id(self, goal_id: str) -> Goal | None:
        if self._goal and self._goal.id == goal_id:
            return self._goal
        return None


class _FakeMatchRepo:
    def __init__(self, matches: list[GoalItemMatch]) -> None:
        self._matches = matches

    async def list_by_goal(
        self,
        goal_id: str,
        min_score: float | None = None,
        since=None,
        rank_mode: RankMode = RankMode.HYBRID,
        half_life_days: float | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[GoalItemMatch], int]:
        filtered = [m for m in self._matches if m.goal_id == goal_id]
        if min_score is not None:
            filtered = [m for m in filtered if m.match_score >= min_score]
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end], len(filtered)


class _FakeItemRepo:
    def __init__(self, items: dict[str, Item]) -> None:
        self._items = items

    async def get_by_ids(self, item_ids: list[str]) -> dict[str, Item]:
        return {
            item_id: self._items[item_id]
            for item_id in item_ids
            if item_id in self._items
        }


class _FakeSourceRepo:
    def __init__(self, sources: dict[str, Source]) -> None:
        self._sources = sources

    async def get_by_ids(self, source_ids: list[str]) -> dict[str, Source]:
        return {
            source_id: self._sources[source_id]
            for source_id in source_ids
            if source_id in self._sources
        }


def _make_item(item_id: str, url: str, source_id: str = "src-1") -> Item:
    return Item(
        id=item_id,
        source_id=source_id,
        url=url,
        url_hash=f"hash-{item_id}",
        title=f"title-{item_id}",
        snippet=None,
        published_at=datetime.now(UTC),
        ingested_at=datetime.now(UTC),
        embedding_status=EmbeddingStatus.DONE,
        embedding=[0.1] * 4,
    )


def _make_match(item_id: str, score: float) -> GoalItemMatch:
    return GoalItemMatch(
        id=f"match-{item_id}",
        goal_id="goal-1",
        item_id=item_id,
        match_score=score,
        features_json={},
        reasons_json={},
        computed_at=datetime.now(UTC),
    )


async def test_list_matches_dedupes_by_topic_and_preserves_best_ranked_item() -> None:
    goal = Goal(
        id="goal-1",
        user_id="user-1",
        name="g",
        description="d",
        status=GoalStatus.ACTIVE,
        priority_mode=PriorityMode.SOFT,
    )
    matches = [
        _make_match("item-1", 0.92),
        _make_match("item-2", 0.91),
        _make_match("item-3", 0.85),
    ]
    items = {
        "item-1": _make_item("item-1", "https://www.v2ex.com/t/100#reply0"),
        "item-2": _make_item("item-2", "https://www.v2ex.com/t/100#reply9"),
        "item-3": _make_item("item-3", "https://www.v2ex.com/t/101#reply1"),
    }
    sources = {
        "src-1": Source(
            id="src-1",
            type=SourceType.RSS,
            name="source",
            owner_id="user-1",
            config={"feed_url": "https://example.com/feed.xml"},
        )
    }

    service = GoalMatchQueryService(
        goal_repository=_FakeGoalRepo(goal),
        match_repository=_FakeMatchRepo(matches),
        item_repository=_FakeItemRepo(items),
        source_repository=_FakeSourceRepo(sources),
    )

    result = await service.list_matches(
        goal_id="goal-1",
        user_id="user-1",
        rank_mode=RankMode.MATCH_SCORE,
        page=1,
        page_size=10,
    )

    assert result.total == 2
    assert [item.item_id for item in result.items] == ["item-1", "item-3"]
