"""AgentOrchestrator（batch/digest）行为测试。"""

import hashlib
from datetime import UTC, datetime
from typing import Any

import pytest

from src.modules.agent.application.llm_service import PushWorthinessOutput
from src.modules.agent.application.orchestrator import AgentOrchestrator
from src.modules.items.domain.entities import EmbeddingStatus, GoalItemMatch, Item

pytestmark = pytest.mark.anyio


class _FakeRunRepo:
    async def create(self, run):
        return run

    async def update(self, run):
        return run


class _FakeToolCallRepo:
    async def create(self, _record) -> None:
        return None

    async def list_by_run(self, _run_id: str) -> list[Any]:
        return []


class _FakeLedgerRepo:
    async def list_by_run(self, _run_id: str) -> list[Any]:
        return []


class _FakeTools:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._run_id: str | None = None

    def set_run_id(self, run_id: str) -> None:
        self._run_id = run_id

    async def call(self, tool_name: str, **kwargs):
        self.calls.append({"tool_name": tool_name, "kwargs": kwargs})
        return type("ToolResult", (), {"success": True, "data": {"id": "d-1"}})()

    def get_call_records(self) -> list[Any]:
        return []


class _FakeGoalRepo:
    async def get_by_id(self, goal_id: str):
        return type(
            "GoalObj",
            (),
            {
                "id": goal_id,
                "user_id": "user-1",
                "name": "goal",
                "description": "python 后端开发",
            },
        )()


class _FakeDecisionRepo:
    def __init__(self, existing_keys: set[str] | None = None) -> None:
        self.existing_keys = existing_keys or set()

    async def get_by_dedupe_key(self, dedupe_key: str):
        if dedupe_key in self.existing_keys:
            return object()
        return None


class _FakeMatchRepo:
    def __init__(self, matches: list[GoalItemMatch]) -> None:
        self.matches = matches
        self.updated_scores: list[float] = []

    async def list_top_by_goal(self, **kwargs) -> list[GoalItemMatch]:
        return self.matches

    async def get_by_goal_and_item(self, goal_id: str, item_id: str):
        for match in self.matches:
            if match.goal_id == goal_id and match.item_id == item_id:
                return match
        return None

    async def update(self, match: GoalItemMatch):
        self.updated_scores.append(match.match_score)
        return match


class _FakeItemRepo:
    def __init__(self, items: dict[str, Item]) -> None:
        self.items = items

    async def get_by_id(self, item_id: str) -> Item | None:
        return self.items.get(item_id)


class _PushLLM:
    async def judge_push_worthiness(self, **kwargs):
        return (
            PushWorthinessOutput(
                label="PUSH",
                confidence=0.9,
                uncertain=False,
                reason="相关",
                evidence=[],
            ),
            None,
        )


def _make_item(item_id: str, url: str) -> Item:
    return Item(
        id=item_id,
        source_id="source-1",
        url=url,
        url_hash=f"hash-{item_id}",
        title=f"title-{item_id}",
        snippet="snippet",
        published_at=datetime.now(UTC),
        ingested_at=datetime.now(UTC),
        embedding_status=EmbeddingStatus.DONE,
        embedding=[0.1] * 4,
    )


def _make_match(item_id: str, score: float = 0.8) -> GoalItemMatch:
    return GoalItemMatch(
        id=f"match-{item_id}",
        goal_id="goal-1",
        item_id=item_id,
        match_score=score,
        features_json={},
        reasons_json={"summary": "match"},
        computed_at=datetime.now(UTC),
    )


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def test_run_digest_skips_when_immediate_or_batch_exists() -> None:
    candidate = _make_match("item-1", score=0.82)
    existing_immediate = _hash_key("goal-1:item-1:IMMEDIATE")

    tools = _FakeTools()
    orchestrator = AgentOrchestrator(
        run_repository=_FakeRunRepo(),
        tool_call_repository=_FakeToolCallRepo(),
        ledger_repository=_FakeLedgerRepo(),
        tools=tools,
        llm_service=_PushLLM(),
    )

    await orchestrator.run_digest(
        goal_id="goal-1",
        match_repository=_FakeMatchRepo([candidate]),
        decision_repository=_FakeDecisionRepo(existing_keys={existing_immediate}),
        goal_repository=_FakeGoalRepo(),
        item_repository=_FakeItemRepo({"item-1": _make_item("item-1", "https://www.v2ex.com/t/1#reply0")}),
        llm_service=_PushLLM(),
    )

    emit_calls = [call for call in tools.calls if call["tool_name"] == "emit_decision"]
    assert emit_calls == []


async def test_run_digest_fails_closed_when_llm_unavailable() -> None:
    candidate = _make_match("item-1", score=0.81)
    tools = _FakeTools()
    orchestrator = AgentOrchestrator(
        run_repository=_FakeRunRepo(),
        tool_call_repository=_FakeToolCallRepo(),
        ledger_repository=_FakeLedgerRepo(),
        tools=tools,
        llm_service=None,
    )

    await orchestrator.run_digest(
        goal_id="goal-1",
        match_repository=_FakeMatchRepo([candidate]),
        decision_repository=_FakeDecisionRepo(),
        goal_repository=_FakeGoalRepo(),
        item_repository=_FakeItemRepo({"item-1": _make_item("item-1", "https://www.v2ex.com/t/1#reply0")}),
        llm_service=None,
    )

    emit_calls = [call for call in tools.calls if call["tool_name"] == "emit_decision"]
    assert len(emit_calls) == 1
    assert emit_calls[0]["kwargs"]["decision"] == "IGNORE"
    assert emit_calls[0]["kwargs"]["status"] == "SKIPPED"


async def test_run_digest_dedupes_same_topic_candidates() -> None:
    candidates = [
        _make_match("item-1", score=0.91),
        _make_match("item-2", score=0.90),
    ]
    tools = _FakeTools()
    orchestrator = AgentOrchestrator(
        run_repository=_FakeRunRepo(),
        tool_call_repository=_FakeToolCallRepo(),
        ledger_repository=_FakeLedgerRepo(),
        tools=tools,
        llm_service=_PushLLM(),
    )

    await orchestrator.run_digest(
        goal_id="goal-1",
        match_repository=_FakeMatchRepo(candidates),
        decision_repository=_FakeDecisionRepo(),
        goal_repository=_FakeGoalRepo(),
        item_repository=_FakeItemRepo(
            {
                "item-1": _make_item("item-1", "https://www.v2ex.com/t/100#reply0"),
                "item-2": _make_item("item-2", "https://www.v2ex.com/t/100#reply8"),
            }
        ),
        llm_service=_PushLLM(),
    )

    emit_calls = [call for call in tools.calls if call["tool_name"] == "emit_decision"]
    assert len(emit_calls) == 1
    assert emit_calls[0]["kwargs"]["item_id"] == "item-1"

