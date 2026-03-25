"""Discovery session service unit tests.

Tests:
- create_session with concurrency limit
- get_session with ownership verification
- add_user_message with status transition
- list_sessions
- expire_stale_sessions
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.modules.agent.application.discovery.session_service import (
    DiscoverySessionService,
)
from src.modules.agent.domain.discovery_entities import (
    CandidateSource,
    DiscoverySession,
    MessageRole,
    SessionStatus,
)
from src.modules.agent.domain.repository import (
    DiscoveryCandidateRepository,
    DiscoverySessionRepository,
)

pytestmark = pytest.mark.anyio


# ============================================
# In-Memory Repository Stubs
# ============================================


class InMemoryDiscoverySessionRepository(DiscoverySessionRepository):
    """In-memory session repository for unit tests."""

    def __init__(self) -> None:
        self._sessions: dict[str, DiscoverySession] = {}

    async def get_by_id(self, entity_id: str) -> DiscoverySession | None:
        s = self._sessions.get(entity_id)
        if s and not s.is_deleted:
            return s
        return None

    async def create(self, entity: DiscoverySession) -> DiscoverySession:
        self._sessions[entity.id] = entity
        return entity

    async def update(self, entity: DiscoverySession) -> DiscoverySession:
        self._sessions[entity.id] = entity
        return entity

    async def delete(self, entity: DiscoverySession | str) -> bool:
        eid = entity if isinstance(entity, str) else entity.id
        if eid in self._sessions:
            self._sessions[eid].is_deleted = True
            return True
        return False

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 10,
        include_deleted: bool = False,
    ) -> tuple[list[DiscoverySession], int]:
        items = [
            s
            for s in self._sessions.values()
            if include_deleted or not s.is_deleted
        ]
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    async def list_by_user(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DiscoverySession], int]:
        items = [
            s
            for s in self._sessions.values()
            if s.user_id == user_id and not s.is_deleted
        ]
        items.sort(key=lambda s: s.created_at, reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    async def count_active_by_user(self, user_id: str) -> int:
        terminal = {SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.EXPIRED}
        return sum(
            1
            for s in self._sessions.values()
            if s.user_id == user_id
            and not s.is_deleted
            and s.status not in terminal
        )


class InMemoryDiscoveryCandidateRepository(DiscoveryCandidateRepository):
    """In-memory candidate repository for unit tests."""

    def __init__(self) -> None:
        self._candidates: dict[str, CandidateSource] = {}

    async def get_by_id(self, entity_id: str) -> CandidateSource | None:
        return self._candidates.get(entity_id)

    async def create(self, entity: CandidateSource) -> CandidateSource:
        self._candidates[entity.id] = entity
        return entity

    async def update(self, entity: CandidateSource) -> CandidateSource:
        self._candidates[entity.id] = entity
        return entity

    async def delete(self, entity: CandidateSource | str) -> bool:
        eid = entity if isinstance(entity, str) else entity.id
        if eid in self._candidates:
            del self._candidates[eid]
            return True
        return False

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 10,
        include_deleted: bool = False,
    ) -> tuple[list[CandidateSource], int]:
        items = list(self._candidates.values())
        return items, len(items)

    async def list_by_session(self, session_id: str) -> list[CandidateSource]:
        return [
            c for c in self._candidates.values() if c.session_id == session_id
        ]


# ============================================
# Fixtures
# ============================================


@pytest.fixture
def session_repo() -> InMemoryDiscoverySessionRepository:
    return InMemoryDiscoverySessionRepository()


@pytest.fixture
def candidate_repo() -> InMemoryDiscoveryCandidateRepository:
    return InMemoryDiscoveryCandidateRepository()


@pytest.fixture
def service(
    session_repo: InMemoryDiscoverySessionRepository,
    candidate_repo: InMemoryDiscoveryCandidateRepository,
) -> DiscoverySessionService:
    return DiscoverySessionService(session_repo, candidate_repo)


# ============================================
# create_session Tests
# ============================================


class TestCreateSession:
    """Test session creation."""

    async def test_create_session_success(
        self, service: DiscoverySessionService
    ):
        session = await service.create_session("user-1", "深圳房产消息")
        assert session.user_id == "user-1"
        assert session.initial_query == "深圳房产消息"
        assert session.status == SessionStatus.ACTIVE
        assert session.expires_at is not None
        assert len(session.messages) == 1
        assert session.messages[0].role == MessageRole.USER
        assert session.messages[0].content == "深圳房产消息"

    async def test_create_session_concurrent_limit(
        self, service: DiscoverySessionService
    ):
        """User cannot have more than 1 active session."""
        await service.create_session("user-1", "First query")
        with pytest.raises(ValueError, match="already has an active"):
            await service.create_session("user-1", "Second query")

    async def test_create_after_completed_session(
        self, service: DiscoverySessionService, session_repo: InMemoryDiscoverySessionRepository
    ):
        """User can create new session after previous one completes."""
        s1 = await service.create_session("user-1", "First query")
        s1.transition_to(SessionStatus.COMPLETED)
        await session_repo.update(s1)

        s2 = await service.create_session("user-1", "Second query")
        assert s2.status == SessionStatus.ACTIVE

    async def test_different_users_can_have_sessions(
        self, service: DiscoverySessionService
    ):
        s1 = await service.create_session("user-1", "Query 1")
        s2 = await service.create_session("user-2", "Query 2")
        assert s1.user_id == "user-1"
        assert s2.user_id == "user-2"


# ============================================
# get_session Tests
# ============================================


class TestGetSession:
    """Test session retrieval with ownership."""

    async def test_get_session_success(
        self, service: DiscoverySessionService
    ):
        created = await service.create_session("user-1", "Test")
        result = await service.get_session(created.id, "user-1")
        assert result is not None
        assert result.id == created.id

    async def test_get_session_wrong_user(
        self, service: DiscoverySessionService
    ):
        created = await service.create_session("user-1", "Test")
        result = await service.get_session(created.id, "user-2")
        assert result is None

    async def test_get_session_not_found(
        self, service: DiscoverySessionService
    ):
        result = await service.get_session("nonexistent-id", "user-1")
        assert result is None


# ============================================
# add_user_message Tests
# ============================================


class TestAddUserMessage:
    """Test adding user messages."""

    async def test_add_message_to_active_session(
        self, service: DiscoverySessionService
    ):
        session = await service.create_session("user-1", "Test")
        updated = await service.add_user_message(session.id, "user-1", "Follow up")
        assert len(updated.messages) == 2
        assert updated.messages[1].content == "Follow up"
        assert updated.status == SessionStatus.ACTIVE

    async def test_add_message_transitions_waiting_to_active(
        self,
        service: DiscoverySessionService,
        session_repo: InMemoryDiscoverySessionRepository,
    ):
        session = await service.create_session("user-1", "Test")
        session.transition_to(SessionStatus.WAITING_USER)
        await session_repo.update(session)

        updated = await service.add_user_message(session.id, "user-1", "确认添加")
        assert updated.status == SessionStatus.ACTIVE

    async def test_add_message_wrong_user(
        self, service: DiscoverySessionService
    ):
        session = await service.create_session("user-1", "Test")
        with pytest.raises(ValueError, match="Session not found"):
            await service.add_user_message(session.id, "user-2", "Hello")

    async def test_add_message_nonexistent_session(
        self, service: DiscoverySessionService
    ):
        with pytest.raises(ValueError, match="Session not found"):
            await service.add_user_message("no-such-id", "user-1", "Hello")


# ============================================
# list_sessions Tests
# ============================================


class TestListSessions:
    """Test session listing."""

    async def test_list_empty(self, service: DiscoverySessionService):
        sessions, total = await service.list_sessions("user-1")
        assert sessions == []
        assert total == 0

    async def test_list_user_sessions(
        self,
        service: DiscoverySessionService,
        session_repo: InMemoryDiscoverySessionRepository,
    ):
        s1 = await service.create_session("user-1", "Query 1")
        # Complete s1 so we can create another
        s1.transition_to(SessionStatus.COMPLETED)
        await session_repo.update(s1)

        await service.create_session("user-1", "Query 2")
        await service.create_session("user-2", "Other user query")

        sessions, total = await service.list_sessions("user-1")
        assert total == 2
        assert all(s.user_id == "user-1" for s in sessions)


# ============================================
# expire_stale_sessions Tests
# ============================================


class TestExpireStaleSessions:
    """Test session expiry."""

    async def test_expire_stale_active_session(
        self,
        service: DiscoverySessionService,
        session_repo: InMemoryDiscoverySessionRepository,
    ):
        session = await service.create_session("user-1", "Test")
        # Make it expired
        session.expires_at = datetime.now(UTC) - timedelta(minutes=5)
        await session_repo.update(session)

        count = await service.expire_stale_sessions()
        assert count == 1

        updated = await session_repo.get_by_id(session.id)
        assert updated is not None
        assert updated.status == SessionStatus.EXPIRED

    async def test_expire_stale_waiting_session(
        self,
        service: DiscoverySessionService,
        session_repo: InMemoryDiscoverySessionRepository,
    ):
        session = await service.create_session("user-1", "Test")
        session.transition_to(SessionStatus.WAITING_USER)
        session.expires_at = datetime.now(UTC) - timedelta(minutes=5)
        await session_repo.update(session)

        count = await service.expire_stale_sessions()
        assert count == 1

    async def test_no_expire_completed_session(
        self,
        service: DiscoverySessionService,
        session_repo: InMemoryDiscoverySessionRepository,
    ):
        session = await service.create_session("user-1", "Test")
        session.transition_to(SessionStatus.COMPLETED)
        session.expires_at = datetime.now(UTC) - timedelta(minutes=5)
        await session_repo.update(session)

        count = await service.expire_stale_sessions()
        assert count == 0

    async def test_no_expire_non_stale_session(
        self, service: DiscoverySessionService
    ):
        await service.create_session("user-1", "Test")
        count = await service.expire_stale_sessions()
        assert count == 0
