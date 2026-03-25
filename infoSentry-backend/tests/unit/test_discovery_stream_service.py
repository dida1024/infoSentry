"""Unit tests for discovery stream state transitions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import FunctionToolResultEvent
from pydantic_ai.messages import ToolReturnPart

from src.modules.agent.application.discovery.stream_service import (
    run_discovery_stream,
)
from src.modules.agent.domain.discovery_entities import (
    DiscoverySession,
    MessageRole,
    SessionStatus,
)

pytestmark = pytest.mark.anyio


def _make_session() -> DiscoverySession:
    session = DiscoverySession(
        user_id="user-1",
        initial_query="测试查询",
        status=SessionStatus.ACTIVE,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add_message(MessageRole.USER, "测试查询")
    return session


class _FakeAgent:
    def __init__(self, events):
        self._events = events

    async def run_stream_events(self, prompt, deps):
        _ = prompt
        _ = deps
        for event in self._events:
            yield event


class TestRunDiscoveryStream:
    async def test_valid_candidate_signal_transitions_to_waiting_user(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        session = _make_session()
        session_repo = AsyncMock()
        session_repo.update = AsyncMock(side_effect=lambda s: s)

        fake_agent = _FakeAgent(
            [
                FunctionToolResultEvent(
                    result=ToolReturnPart(
                        tool_name="validate_source",
                        tool_call_id="call-1",
                        content={
                            "_signal": "candidates_valid",
                            "candidate_id": "cand-1",
                        },
                    ),
                    content={"_signal": "candidates_valid", "candidate_id": "cand-1"},
                ),
            ]
        )
        monkeypatch.setattr(
            "src.modules.agent.application.discovery.stream_service.get_discovery_agent",
            lambda: fake_agent,
        )

        events = []
        async for event in run_discovery_stream(
            session=session,
            session_repo=session_repo,
            candidate_repo=AsyncMock(),
            source_repository=AsyncMock(),
            catalog_provider=AsyncMock(),
            create_source_handler=AsyncMock(),
            subscribe_source_handler=AsyncMock(),
            source_query_service=AsyncMock(),
            create_fetcher=MagicMock(),
        ):
            events.append(event)

        assert session.status == SessionStatus.WAITING_USER
        assert any(event["event"] == "confirm_required" for event in events)
        session_repo.update.assert_awaited()

    async def test_source_added_signal_transitions_to_completed(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        session = _make_session()
        session_repo = AsyncMock()
        session_repo.update = AsyncMock(side_effect=lambda s: s)

        fake_agent = _FakeAgent(
            [
                FunctionToolResultEvent(
                    result=ToolReturnPart(
                        tool_name="add_source",
                        tool_call_id="call-2",
                        content={"_signal": "source_added", "source_id": "src-1"},
                    ),
                    content={"_signal": "source_added", "source_id": "src-1"},
                ),
            ]
        )
        monkeypatch.setattr(
            "src.modules.agent.application.discovery.stream_service.get_discovery_agent",
            lambda: fake_agent,
        )

        events = []
        async for event in run_discovery_stream(
            session=session,
            session_repo=session_repo,
            candidate_repo=AsyncMock(),
            source_repository=AsyncMock(),
            catalog_provider=AsyncMock(),
            create_source_handler=AsyncMock(),
            subscribe_source_handler=AsyncMock(),
            source_query_service=AsyncMock(),
            create_fetcher=MagicMock(),
        ):
            events.append(event)

        assert session.status == SessionStatus.COMPLETED
        assert any(event["event"] == "session_completed" for event in events)
        session_repo.update.assert_awaited()
