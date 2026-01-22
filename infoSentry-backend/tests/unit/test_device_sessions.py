"""Tests for device session refresh flow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.core.infrastructure.security.jwt import JWTTokenService
from src.modules.users.application.commands import (
    RefreshSessionCommand,
    RevokeSessionCommand,
)
from src.modules.users.application.handlers import (
    RefreshSessionHandler,
    RevokeSessionHandler,
)
from src.modules.users.application.session_service import (
    generate_refresh_token,
    hash_refresh_token,
)
from src.modules.users.domain.entities import DeviceSession, User
from src.modules.users.domain.exceptions import (
    DeviceSessionExpiredError,
    DeviceSessionRiskBlockedError,
)
from src.modules.users.domain.repository import DeviceSessionRepository, UserRepository


class InMemoryUserRepository(UserRepository):
    """In-memory user repository for tests."""

    def __init__(self, users: dict[str, User] | None = None) -> None:
        self.users = users or {}

    async def get_by_id(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    async def exists_by_email(self, email: str) -> bool:
        return any(user.email == email for user in self.users.values())

    async def create(self, user: User) -> User:
        self.users[user.id] = user
        return user

    async def update(self, user: User) -> User:
        self.users[user.id] = user
        return user

    async def delete(self, user: User | str) -> bool:
        user_id = user.id if isinstance(user, User) else user
        return self.users.pop(user_id, None) is not None

    async def list_all(
        self, page: int = 1, page_size: int = 10, include_deleted: bool = False
    ) -> tuple[list[User], int]:
        users = list(self.users.values())
        return users, len(users)


class InMemoryDeviceSessionRepository(DeviceSessionRepository):
    """In-memory device session repository for tests."""

    def __init__(self, sessions: dict[str, DeviceSession] | None = None) -> None:
        self.sessions = sessions or {}
        self.hash_index = {
            session.refresh_token_hash: session.id for session in self.sessions.values()
        }

    async def get_by_id(self, session_id: str) -> DeviceSession | None:
        return self.sessions.get(session_id)

    async def get_by_refresh_token_hash(
        self, refresh_token_hash: str
    ) -> DeviceSession | None:
        session_id = self.hash_index.get(refresh_token_hash)
        if not session_id:
            return None
        return self.sessions.get(session_id)

    async def create(self, session: DeviceSession) -> DeviceSession:
        self.sessions[session.id] = session
        self.hash_index[session.refresh_token_hash] = session.id
        return session

    async def update(self, session: DeviceSession) -> DeviceSession:
        existing = self.sessions.get(session.id)
        if existing:
            self.hash_index.pop(existing.refresh_token_hash, None)
        self.sessions[session.id] = session
        self.hash_index[session.refresh_token_hash] = session.id
        return session

    async def delete(self, session: DeviceSession | str) -> bool:
        session_id = session.id if isinstance(session, DeviceSession) else session
        existing = self.sessions.pop(session_id, None)
        if not existing:
            return False
        self.hash_index.pop(existing.refresh_token_hash, None)
        return True

    async def list_all(
        self, page: int = 1, page_size: int = 10, include_deleted: bool = False
    ) -> tuple[list[DeviceSession], int]:
        sessions = list(self.sessions.values())
        return sessions, len(sessions)


@pytest.mark.anyio
async def test_refresh_session_rotates_token() -> None:
    user = User(id="user-1", email="user@example.com")
    user_repo = InMemoryUserRepository({user.id: user})

    refresh_token = generate_refresh_token()
    refresh_hash = hash_refresh_token(refresh_token)
    now = datetime.now(UTC)
    session = DeviceSession(
        id="session-1",
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        device_id="device-1",
        user_agent="TestAgent",
        ip_address="127.0.0.1",
        expires_at=now + timedelta(days=1),
        last_seen_at=now,
    )
    session_repo = InMemoryDeviceSessionRepository({session.id: session})

    handler = RefreshSessionHandler(user_repo, session_repo, JWTTokenService())
    access_token, payload = await handler.handle(
        RefreshSessionCommand(
            refresh_token=refresh_token,
            ip_address="127.0.0.1",
            user_agent="TestAgent",
        )
    )

    assert access_token
    assert payload.token != refresh_token

    updated = await session_repo.get_by_id(session.id)
    assert updated is not None
    assert updated.refresh_token_hash != refresh_hash
    assert updated.expires_at > now


@pytest.mark.anyio
async def test_refresh_session_risk_revokes() -> None:
    user = User(id="user-2", email="risk@example.com")
    user_repo = InMemoryUserRepository({user.id: user})

    refresh_token = generate_refresh_token()
    refresh_hash = hash_refresh_token(refresh_token)
    now = datetime.now(UTC)
    session = DeviceSession(
        id="session-2",
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        device_id="device-2",
        user_agent="SafeAgent",
        ip_address="10.0.0.1",
        expires_at=now + timedelta(days=1),
        last_seen_at=now,
    )
    session_repo = InMemoryDeviceSessionRepository({session.id: session})

    handler = RefreshSessionHandler(user_repo, session_repo, JWTTokenService())
    with pytest.raises(DeviceSessionRiskBlockedError):
        await handler.handle(
            RefreshSessionCommand(
                refresh_token=refresh_token,
                ip_address="10.0.0.2",
                user_agent="SafeAgent",
            )
        )

    updated = await session_repo.get_by_id(session.id)
    assert updated is not None
    assert updated.revoked_at is not None


@pytest.mark.anyio
async def test_refresh_session_expired() -> None:
    user = User(id="user-3", email="expired@example.com")
    user_repo = InMemoryUserRepository({user.id: user})

    refresh_token = generate_refresh_token()
    refresh_hash = hash_refresh_token(refresh_token)
    now = datetime.now(UTC)
    session = DeviceSession(
        id="session-3",
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        device_id="device-3",
        user_agent="Agent",
        ip_address="192.168.1.10",
        expires_at=now - timedelta(minutes=1),
        last_seen_at=now,
    )
    session_repo = InMemoryDeviceSessionRepository({session.id: session})

    handler = RefreshSessionHandler(user_repo, session_repo, JWTTokenService())
    with pytest.raises(DeviceSessionExpiredError):
        await handler.handle(
            RefreshSessionCommand(
                refresh_token=refresh_token,
                ip_address="192.168.1.10",
                user_agent="Agent",
            )
        )


@pytest.mark.anyio
async def test_revoke_session_missing() -> None:
    session_repo = InMemoryDeviceSessionRepository()
    handler = RevokeSessionHandler(session_repo)

    result = await handler.handle(RevokeSessionCommand(refresh_token="missing"))
    assert result is False
