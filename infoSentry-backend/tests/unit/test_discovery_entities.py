"""Discovery domain entity unit tests.

Tests:
- DiscoverySession status transitions
- DiscoverySession message management
- DiscoverySession expiry logic
- CandidateSource lifecycle (mark_valid, mark_invalid, accept, reject)
- SessionMessage creation
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.modules.agent.domain.discovery_entities import (
    CandidateSource,
    CandidateStatus,
    DiscoverySession,
    MessageRole,
    SessionMessage,
    SessionStatus,
)

pytestmark = pytest.mark.anyio


# ============================================
# SessionMessage Tests
# ============================================


class TestSessionMessage:
    """SessionMessage creation tests."""

    def test_create_user_message(self):
        msg = SessionMessage(role=MessageRole.USER, content="Hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"
        assert msg.metadata is None
        assert msg.id is not None

    def test_create_message_with_metadata(self):
        msg = SessionMessage(
            role=MessageRole.AGENT,
            content="Found sources",
            metadata={"tool_calls": ["search_catalog"]},
        )
        assert msg.metadata == {"tool_calls": ["search_catalog"]}

    def test_create_system_message(self):
        msg = SessionMessage(role=MessageRole.SYSTEM, content="Session expired")
        assert msg.role == MessageRole.SYSTEM


# ============================================
# DiscoverySession Tests
# ============================================


class TestDiscoverySession:
    """DiscoverySession lifecycle tests."""

    @pytest.fixture
    def session(self) -> DiscoverySession:
        return DiscoverySession(
            user_id="user-1",
            initial_query="深圳房产相关消息",
            status=SessionStatus.ACTIVE,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

    def test_create_session(self, session: DiscoverySession):
        assert session.user_id == "user-1"
        assert session.initial_query == "深圳房产相关消息"
        assert session.status == SessionStatus.ACTIVE
        assert session.messages == []
        assert session.id is not None

    # --- Status transitions ---

    def test_active_to_waiting_user(self, session: DiscoverySession):
        session.transition_to(SessionStatus.WAITING_USER)
        assert session.status == SessionStatus.WAITING_USER

    def test_active_to_completed(self, session: DiscoverySession):
        session.transition_to(SessionStatus.COMPLETED)
        assert session.status == SessionStatus.COMPLETED

    def test_active_to_failed(self, session: DiscoverySession):
        session.transition_to(SessionStatus.FAILED)
        assert session.status == SessionStatus.FAILED

    def test_active_to_expired(self, session: DiscoverySession):
        session.transition_to(SessionStatus.EXPIRED)
        assert session.status == SessionStatus.EXPIRED

    def test_waiting_user_to_active(self, session: DiscoverySession):
        session.transition_to(SessionStatus.WAITING_USER)
        session.transition_to(SessionStatus.ACTIVE)
        assert session.status == SessionStatus.ACTIVE

    def test_waiting_user_to_expired(self, session: DiscoverySession):
        session.transition_to(SessionStatus.WAITING_USER)
        session.transition_to(SessionStatus.EXPIRED)
        assert session.status == SessionStatus.EXPIRED

    def test_invalid_transition_completed_to_active(self, session: DiscoverySession):
        session.transition_to(SessionStatus.COMPLETED)
        with pytest.raises(ValueError, match="Invalid transition"):
            session.transition_to(SessionStatus.ACTIVE)

    def test_invalid_transition_failed_to_active(self, session: DiscoverySession):
        session.transition_to(SessionStatus.FAILED)
        with pytest.raises(ValueError, match="Invalid transition"):
            session.transition_to(SessionStatus.ACTIVE)

    def test_invalid_transition_expired_to_active(self, session: DiscoverySession):
        session.transition_to(SessionStatus.EXPIRED)
        with pytest.raises(ValueError, match="Invalid transition"):
            session.transition_to(SessionStatus.ACTIVE)

    def test_invalid_transition_active_to_active(self, session: DiscoverySession):
        with pytest.raises(ValueError, match="Invalid transition"):
            session.transition_to(SessionStatus.ACTIVE)

    def test_invalid_transition_waiting_to_completed(self, session: DiscoverySession):
        session.transition_to(SessionStatus.WAITING_USER)
        with pytest.raises(ValueError, match="Invalid transition"):
            session.transition_to(SessionStatus.COMPLETED)

    # --- Message management ---

    def test_add_message(self, session: DiscoverySession):
        session.add_message(MessageRole.USER, "Test message")
        assert len(session.messages) == 1
        assert session.messages[0].role == MessageRole.USER
        assert session.messages[0].content == "Test message"

    def test_add_message_with_metadata(self, session: DiscoverySession):
        session.add_message(
            MessageRole.AGENT, "Found sources", tool_calls=["search_catalog"]
        )
        assert len(session.messages) == 1
        assert session.messages[0].metadata == {"tool_calls": ["search_catalog"]}

    def test_add_multiple_messages(self, session: DiscoverySession):
        session.add_message(MessageRole.USER, "Find RSS feeds")
        session.add_message(MessageRole.AGENT, "Searching...")
        session.add_message(MessageRole.AGENT, "Found 2 sources")
        assert len(session.messages) == 3

    def test_add_message_updates_timestamp(self, session: DiscoverySession):
        old_updated = session.updated_at
        session.add_message(MessageRole.USER, "Test")
        assert session.updated_at >= old_updated

    # --- Expiry logic ---

    def test_is_expired_when_past_ttl(self, session: DiscoverySession):
        session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        assert session.is_expired(datetime.now(UTC)) is True

    def test_is_not_expired_when_within_ttl(self, session: DiscoverySession):
        session.expires_at = datetime.now(UTC) + timedelta(hours=1)
        assert session.is_expired(datetime.now(UTC)) is False

    def test_is_not_expired_when_no_expiry(self, session: DiscoverySession):
        session.expires_at = None
        assert session.is_expired(datetime.now(UTC)) is False

    def test_transition_updates_timestamp(self, session: DiscoverySession):
        old_updated = session.updated_at
        session.transition_to(SessionStatus.WAITING_USER)
        assert session.updated_at >= old_updated


# ============================================
# CandidateSource Tests
# ============================================


class TestCandidateSource:
    """CandidateSource lifecycle tests."""

    @pytest.fixture
    def candidate(self) -> CandidateSource:
        return CandidateSource(
            session_id="session-1",
            source_type="RSS",
            name="Tech Blog RSS",
            url="https://example.com/feed.xml",
            config={"feed_url": "https://example.com/feed.xml"},
            discovered_via="rss_probe",
        )

    def test_create_candidate(self, candidate: CandidateSource):
        assert candidate.session_id == "session-1"
        assert candidate.source_type == "RSS"
        assert candidate.status == CandidateStatus.DISCOVERED
        assert candidate.source_id is None
        assert candidate.validation_result is None

    def test_mark_valid(self, candidate: CandidateSource):
        result = {"valid": True, "items_count": 10, "sample_titles": ["Title 1"]}
        candidate.mark_valid(result)
        assert candidate.status == CandidateStatus.VALID
        assert candidate.validation_result == result

    def test_mark_invalid(self, candidate: CandidateSource):
        result = {"valid": False, "error": "Connection timeout"}
        candidate.mark_invalid(result)
        assert candidate.status == CandidateStatus.INVALID
        assert candidate.validation_result == result

    def test_accept(self, candidate: CandidateSource):
        candidate.mark_valid({"valid": True})
        candidate.accept("source-abc")
        assert candidate.status == CandidateStatus.ACCEPTED
        assert candidate.source_id == "source-abc"

    def test_reject(self, candidate: CandidateSource):
        candidate.mark_valid({"valid": True})
        candidate.reject()
        assert candidate.status == CandidateStatus.REJECTED
        assert candidate.source_id is None

    def test_mark_valid_updates_timestamp(self, candidate: CandidateSource):
        old_updated = candidate.updated_at
        candidate.mark_valid({"valid": True})
        assert candidate.updated_at >= old_updated

    def test_discovered_via_values(self):
        """Test various discovery channels."""
        for channel in ("catalog", "rss_probe", "rsshub", "site_analysis"):
            c = CandidateSource(
                session_id="s1",
                source_type="RSS",
                name="Test",
                url="https://example.com",
                discovered_via=channel,
            )
            assert c.discovered_via == channel
