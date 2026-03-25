"""Discovery API endpoint unit tests.

Tests:
- POST /discovery/sessions → 201 / 409
- GET /discovery/sessions/{id} → 200 / 404
- GET /discovery/sessions/{id}/stream → 200 / 404
- POST /discovery/sessions/{id}/messages → 200 / 400
- GET /discovery/sessions → 200
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.domain.exceptions import DuplicateEntityError
from src.modules.agent.domain.discovery_entities import (
    DiscoverySession,
    MessageRole,
    SessionStatus,
)

pytestmark = pytest.mark.anyio


# ============================================
# Fixtures
# ============================================


@pytest.fixture
def mock_session_service():
    """Mock DiscoverySessionService."""
    return AsyncMock()


@pytest.fixture
def mock_candidate_repo():
    """Mock DiscoveryCandidateRepository."""
    repo = AsyncMock()
    repo.list_by_session = AsyncMock(return_value=[])
    return repo


def _make_session(
    user_id: str = "user-1",
    query: str = "Test query",
    status: SessionStatus = SessionStatus.ACTIVE,
) -> DiscoverySession:
    session = DiscoverySession(
        user_id=user_id,
        initial_query=query,
        status=status,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add_message(MessageRole.USER, query)
    return session


@pytest.fixture
async def client(
    mock_session_service,
    mock_candidate_repo,
) -> AsyncClient:
    """HTTP client with mocked dependencies."""
    from main import app
    from src.core.application.security import get_current_user_id
    from src.modules.agent.application.discovery.dependencies import (
        get_catalog_provider,
        get_discovery_candidate_repository,
        get_discovery_session_repository,
        get_discovery_session_service,
        get_fetcher_creator,
    )
    from src.modules.sources.application.dependencies import (
        get_create_source_handler,
        get_source_query_service,
        get_source_repository,
        get_subscribe_source_handler,
    )

    app.dependency_overrides[get_current_user_id] = lambda: "user-1"
    app.dependency_overrides[get_discovery_session_service] = (
        lambda: mock_session_service
    )
    app.dependency_overrides[get_discovery_candidate_repository] = (
        lambda: mock_candidate_repo
    )
    # SSE stream endpoint needs these additional overrides
    app.dependency_overrides[get_discovery_session_repository] = (
        lambda: AsyncMock()
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
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ============================================
# POST /discovery/sessions Tests
# ============================================


class TestCreateSessionEndpoint:
    """POST /api/v1/discovery/sessions"""

    async def test_create_session_201(
        self, client: AsyncClient, mock_session_service
    ):
        session = _make_session()
        mock_session_service.create_session = AsyncMock(return_value=session)

        resp = await client.post(
            "/api/v1/discovery/sessions",
            json={"query": "深圳房产消息"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["status"] == "active"
        assert body["data"]["initial_query"] == "Test query"

    async def test_create_session_409_concurrent(
        self, client: AsyncClient, mock_session_service
    ):
        mock_session_service.create_session = AsyncMock(
            side_effect=ValueError("User already has an active discovery session")
        )

        resp = await client.post(
            "/api/v1/discovery/sessions",
            json={"query": "Second session"},
        )
        assert resp.status_code == 409

    async def test_create_session_409_duplicate_entity(
        self, client: AsyncClient, mock_session_service
    ):
        mock_session_service.create_session = AsyncMock(
            side_effect=DuplicateEntityError(
                "DiscoverySession",
                "user_id",
                "user-1",
            )
        )

        resp = await client.post(
            "/api/v1/discovery/sessions",
            json={"query": "Second session"},
        )
        assert resp.status_code == 409


# ============================================
# GET /discovery/sessions/{id} Tests
# ============================================


class TestGetSessionEndpoint:
    """GET /api/v1/discovery/sessions/{session_id}"""

    async def test_get_session_200(
        self, client: AsyncClient, mock_session_service, mock_candidate_repo
    ):
        session = _make_session()
        mock_session_service.get_session = AsyncMock(return_value=session)

        resp = await client.get(f"/api/v1/discovery/sessions/{session.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == session.id
        assert len(body["data"]["messages"]) == 1

    async def test_get_session_404(
        self, client: AsyncClient, mock_session_service
    ):
        mock_session_service.get_session = AsyncMock(return_value=None)

        resp = await client.get("/api/v1/discovery/sessions/nonexistent")
        assert resp.status_code == 404


# ============================================
# GET /discovery/sessions/{id}/stream Tests
# ============================================


class TestStreamSessionEndpoint:
    """GET /api/v1/discovery/sessions/{session_id}/stream"""

    async def test_stream_404(
        self, client: AsyncClient, mock_session_service
    ):
        mock_session_service.get_session = AsyncMock(return_value=None)

        resp = await client.get("/api/v1/discovery/sessions/nonexistent/stream")
        assert resp.status_code == 404

    async def test_stream_400_completed_session(
        self, client: AsyncClient, mock_session_service
    ):
        session = _make_session(status=SessionStatus.COMPLETED)
        mock_session_service.get_session = AsyncMock(return_value=session)

        resp = await client.get(f"/api/v1/discovery/sessions/{session.id}/stream")
        assert resp.status_code == 400


# ============================================
# POST /discovery/sessions/{id}/messages Tests
# ============================================


class TestSendMessageEndpoint:
    """POST /api/v1/discovery/sessions/{session_id}/messages"""

    async def test_send_message_200(
        self, client: AsyncClient, mock_session_service
    ):
        session = _make_session()
        mock_session_service.add_user_message = AsyncMock(return_value=session)

        resp = await client.post(
            f"/api/v1/discovery/sessions/{session.id}/messages",
            json={"content": "确认添加"},
        )
        assert resp.status_code == 200

    async def test_send_message_400_not_found(
        self, client: AsyncClient, mock_session_service
    ):
        mock_session_service.add_user_message = AsyncMock(
            side_effect=ValueError("Session not found")
        )

        resp = await client.post(
            "/api/v1/discovery/sessions/nonexistent/messages",
            json={"content": "Hello"},
        )
        assert resp.status_code == 400


# ============================================
# GET /discovery/sessions Tests
# ============================================


class TestListSessionsEndpoint:
    """GET /api/v1/discovery/sessions"""

    async def test_list_sessions_200(
        self, client: AsyncClient, mock_session_service
    ):
        s1 = _make_session(query="Query 1")
        s2 = _make_session(query="Query 2", status=SessionStatus.COMPLETED)
        mock_session_service.list_sessions = AsyncMock(
            return_value=([s1, s2], 2)
        )

        resp = await client.get("/api/v1/discovery/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 2
        assert len(body["data"]) == 2

    async def test_list_sessions_empty(
        self, client: AsyncClient, mock_session_service
    ):
        mock_session_service.list_sessions = AsyncMock(return_value=([], 0))

        resp = await client.get("/api/v1/discovery/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0
        assert body["data"] == []
