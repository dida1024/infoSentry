"""App-level E2E tests for the discovery flow.

These tests exercise the real FastAPI routes plus SSE streaming while using
in-memory repositories and a deterministic fake agent. The goal is to verify
the user-visible discovery lifecycle end-to-end:

create session -> stream validation -> waiting confirmation -> send confirm
message -> stream add source -> completed -> reconnect state recovery
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai import FunctionToolResultEvent
from pydantic_ai.messages import ToolReturnPart

from src.modules.agent.domain.discovery_entities import (
    CandidateSource,
    CandidateStatus,
    MessageRole,
)
from tests.unit.test_discovery_session_service import (
    InMemoryDiscoveryCandidateRepository,
    InMemoryDiscoverySessionRepository,
)

pytestmark = [pytest.mark.anyio, pytest.mark.e2e]


class _DiscoveryFlowAgent:
    """Deterministic fake agent for driving the real SSE route."""

    async def run_stream_events(
        self,
        prompt: str,
        deps: object,
    ) -> AsyncGenerator[FunctionToolResultEvent, None]:
        _ = prompt
        session = deps.session
        candidate_repo = deps.candidate_repository

        latest_user_message = next(
            message.content
            for message in reversed(session.messages)
            if message.role == MessageRole.USER
        )

        if latest_user_message == session.initial_query:
            candidate = CandidateSource(
                session_id=session.id,
                source_type="RSS",
                name="AI Feed",
                url="https://example.com/feed.xml",
                config={"feed_url": "https://example.com/feed.xml"},
                status=CandidateStatus.VALIDATING,
                discovered_via="rss_probe",
            )
            await candidate_repo.create(candidate)
            candidate.mark_valid(
                {
                    "fetch_ok": True,
                    "title": "AI Feed",
                    "item_count": 12,
                }
            )
            await candidate_repo.update(candidate)
            yield FunctionToolResultEvent(
                result=ToolReturnPart(
                    tool_name="validate_source",
                    tool_call_id="call-validate",
                    content={
                        "_signal": "candidates_valid",
                        "candidate_id": candidate.id,
                    },
                ),
                content={
                    "_signal": "candidates_valid",
                    "candidate_id": candidate.id,
                },
            )
            return

        candidates = await candidate_repo.list_by_session(session.id)
        assert len(candidates) == 1
        candidate = candidates[0]
        candidate.accept("source-e2e-001")
        await candidate_repo.update(candidate)
        yield FunctionToolResultEvent(
            result=ToolReturnPart(
                tool_name="add_source",
                tool_call_id="call-add",
                content={
                    "_signal": "source_added",
                    "source_id": "source-e2e-001",
                    "candidate_id": candidate.id,
                },
            ),
            content={
                "_signal": "source_added",
                "source_id": "source-e2e-001",
                "candidate_id": candidate.id,
            },
        )


@pytest.fixture
def session_repo() -> InMemoryDiscoverySessionRepository:
    return InMemoryDiscoverySessionRepository()


@pytest.fixture
def candidate_repo() -> InMemoryDiscoveryCandidateRepository:
    return InMemoryDiscoveryCandidateRepository()


@pytest.fixture
async def client(
    session_repo: InMemoryDiscoverySessionRepository,
    candidate_repo: InMemoryDiscoveryCandidateRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    from main import app
    from src.core.application.security import get_current_user_id
    from src.modules.agent.application.discovery.dependencies import (
        get_catalog_provider,
        get_discovery_candidate_repository,
        get_discovery_session_repository,
        get_discovery_session_service,
        get_fetcher_creator,
    )
    from src.modules.agent.application.discovery.session_service import (
        DiscoverySessionService,
    )
    from src.modules.sources.application.dependencies import (
        get_create_source_handler,
        get_source_query_service,
        get_source_repository,
        get_subscribe_source_handler,
    )

    service = DiscoverySessionService(session_repo, candidate_repo)
    original_overrides = dict(app.dependency_overrides)

    monkeypatch.setattr(
        "src.modules.agent.application.discovery.stream_service.get_discovery_agent",
        lambda: _DiscoveryFlowAgent(),
    )

    app.dependency_overrides[get_current_user_id] = lambda: "user-e2e-1"
    app.dependency_overrides[get_discovery_session_service] = lambda: service
    app.dependency_overrides[get_discovery_session_repository] = lambda: session_repo
    app.dependency_overrides[get_discovery_candidate_repository] = (
        lambda: candidate_repo
    )
    app.dependency_overrides[get_source_repository] = lambda: AsyncMock()
    app.dependency_overrides[get_create_source_handler] = lambda: AsyncMock()
    app.dependency_overrides[get_subscribe_source_handler] = lambda: AsyncMock()
    app.dependency_overrides[get_source_query_service] = lambda: AsyncMock()
    app.dependency_overrides[get_catalog_provider] = lambda: AsyncMock()
    app.dependency_overrides[get_fetcher_creator] = lambda: MagicMock()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


async def _read_sse_events(
    client: AsyncClient,
    session_id: str,
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []

    async with client.stream(
        "GET",
        f"/api/v1/discovery/sessions/{session_id}/stream",
    ) as response:
        assert response.status_code == 200

        current_event: str | None = None
        current_data: str | None = None

        async for line in response.aiter_lines():
            if line.startswith("event:"):
                current_event = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                current_data = line.removeprefix("data:").strip()
            elif line == "" and current_event is not None and current_data is not None:
                events.append(
                    {
                        "event": current_event,
                        "data": json.loads(current_data),
                    }
                )
                current_event = None
                current_data = None

    return events


class TestDiscoveryFlowE2E:
    async def test_discovery_flow_end_to_end(
        self,
        client: AsyncClient,
        candidate_repo: InMemoryDiscoveryCandidateRepository,
    ) -> None:
        create_response = await client.post(
            "/api/v1/discovery/sessions",
            json={"query": "帮我找 AI 行业新闻 RSS"},
        )
        assert create_response.status_code == 201
        session_id = create_response.json()["data"]["id"]

        first_stream_events = await _read_sse_events(client, session_id)
        assert any(event["event"] == "tool_result" for event in first_stream_events)
        assert any(
            event["event"] == "confirm_required" for event in first_stream_events
        )

        waiting_detail = await client.get(f"/api/v1/discovery/sessions/{session_id}")
        assert waiting_detail.status_code == 200
        waiting_payload = waiting_detail.json()["data"]
        assert waiting_payload["status"] == "waiting_user"
        assert len(waiting_payload["candidates"]) == 1
        candidate = waiting_payload["candidates"][0]
        assert candidate["status"] == "valid"
        assert candidate["source_id"] is None

        confirm_response = await client.post(
            f"/api/v1/discovery/sessions/{session_id}/messages",
            json={"content": "确认添加这个源"},
        )
        assert confirm_response.status_code == 200
        assert confirm_response.json()["data"]["status"] == "active"

        second_stream_events = await _read_sse_events(client, session_id)
        assert any(event["event"] == "tool_result" for event in second_stream_events)
        assert any(
            event["event"] == "session_completed" for event in second_stream_events
        )

        completed_detail = await client.get(f"/api/v1/discovery/sessions/{session_id}")
        assert completed_detail.status_code == 200
        completed_payload = completed_detail.json()["data"]
        assert completed_payload["status"] == "completed"
        assert len(completed_payload["messages"]) >= 2
        assert completed_payload["candidates"][0]["status"] == "accepted"
        assert completed_payload["candidates"][0]["source_id"] == "source-e2e-001"

        persisted_candidates = await candidate_repo.list_by_session(session_id)
        assert len(persisted_candidates) == 1
        assert persisted_candidates[0].status == CandidateStatus.ACCEPTED
        assert persisted_candidates[0].source_id == "source-e2e-001"

    async def test_completed_session_stream_is_rejected(
        self,
        client: AsyncClient,
    ) -> None:
        create_response = await client.post(
            "/api/v1/discovery/sessions",
            json={"query": "帮我找科技博客 RSS"},
        )
        assert create_response.status_code == 201
        session_id = create_response.json()["data"]["id"]

        await _read_sse_events(client, session_id)
        await client.post(
            f"/api/v1/discovery/sessions/{session_id}/messages",
            json={"content": "确认添加"},
        )
        await _read_sse_events(client, session_id)

        rejected_response = await client.get(
            f"/api/v1/discovery/sessions/{session_id}/stream"
        )
        assert rejected_response.status_code == 400
