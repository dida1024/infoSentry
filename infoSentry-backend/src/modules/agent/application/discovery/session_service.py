"""Discovery session management service."""

from datetime import UTC, datetime, timedelta

from src.core.config import settings
from src.modules.agent.domain.discovery_entities import (
    DiscoverySession,
    MessageRole,
    SessionStatus,
)
from src.modules.agent.domain.repository import (
    DiscoveryCandidateRepository,
    DiscoverySessionRepository,
)


class DiscoverySessionService:
    """Manages discovery session lifecycle."""

    def __init__(
        self,
        session_repository: DiscoverySessionRepository,
        candidate_repository: DiscoveryCandidateRepository,
    ):
        self._session_repo = session_repository
        self._candidate_repo = candidate_repository

    async def create_session(
        self,
        user_id: str,
        query: str,
    ) -> DiscoverySession:
        """Create a new discovery session.

        Raises ValueError if user already has an active session.
        """
        active_count = await self._session_repo.count_active_by_user(user_id)
        if active_count >= 1:
            raise ValueError("User already has an active discovery session")

        now = datetime.now(UTC)
        session = DiscoverySession(
            user_id=user_id,
            initial_query=query,
            status=SessionStatus.ACTIVE,
            expires_at=now + timedelta(seconds=settings.DISCOVERY_SESSION_TTL_SEC),
        )
        session.add_message(MessageRole.USER, query)
        return await self._session_repo.create(session)

    async def get_session(
        self,
        session_id: str,
        user_id: str,
    ) -> DiscoverySession | None:
        """Get a session, verifying ownership."""
        session = await self._session_repo.get_by_id(session_id)
        if session is None or session.user_id != user_id:
            return None
        return session

    async def add_user_message(
        self,
        session_id: str,
        user_id: str,
        content: str,
    ) -> DiscoverySession:
        """Add a user message and transition waiting_user -> active."""
        session = await self.get_session(session_id, user_id)
        if session is None:
            raise ValueError("Session not found")

        if session.status == SessionStatus.WAITING_USER:
            session.transition_to(SessionStatus.ACTIVE)

        session.add_message(MessageRole.USER, content)
        return await self._session_repo.update(session)

    async def update_status(
        self,
        session_id: str,
        status: SessionStatus,
    ) -> DiscoverySession:
        """Update session status."""
        session = await self._session_repo.get_by_id(session_id)
        if session is None:
            raise ValueError("Session not found")
        session.transition_to(status)
        return await self._session_repo.update(session)

    async def list_sessions(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DiscoverySession], int]:
        """List sessions for a user."""
        return await self._session_repo.list_by_user(user_id, page, page_size)

    async def expire_stale_sessions(self) -> int:
        """Expire sessions that have passed their TTL. Returns count expired.

        Paginates through all sessions to ensure full coverage.
        """
        now = datetime.now(UTC)
        expired_count = 0
        page = 1
        page_size = 100

        while True:
            sessions, total = await self._session_repo.list_all(
                page=page, page_size=page_size
            )
            if not sessions:
                break

            for session in sessions:
                if session.is_expired(now) and session.status in (
                    SessionStatus.ACTIVE,
                    SessionStatus.WAITING_USER,
                ):
                    session.transition_to(SessionStatus.EXPIRED)
                    await self._session_repo.update(session)
                    expired_count += 1

            if page * page_size >= total:
                break
            page += 1

        return expired_count
