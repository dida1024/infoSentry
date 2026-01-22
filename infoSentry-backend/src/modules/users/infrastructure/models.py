"""User database models."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, Text, UniqueConstraint
from sqlmodel import Field

from src.core.infrastructure.database.base_model import BaseModel
from src.modules.users.domain.entities import UserStatus


class UserModel(BaseModel, table=True):
    """User database model."""

    __tablename__ = "users"

    email: str = Field(index=True, nullable=False, unique=True)
    is_active: bool = Field(default=True, nullable=False)
    status: UserStatus = Field(
        default=UserStatus.ACTIVE,
        sa_type=Enum(
            UserStatus,
            name="userstatus",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
    )
    last_login_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )
    display_name: str | None = Field(default=None, nullable=True)
    timezone: str = Field(default="Asia/Shanghai", nullable=False)


class MagicLinkModel(BaseModel, table=True):
    """Magic link database model."""

    __tablename__ = "auth_magic_links"

    email: str = Field(index=True, nullable=False)
    token: str = Field(index=True, nullable=False, unique=True)
    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    is_used: bool = Field(default=False, nullable=False)
    used_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )


class DeviceSessionModel(BaseModel, table=True):
    """Device session database model."""

    __tablename__ = "user_device_sessions"

    user_id: str = Field(nullable=False, index=True)
    refresh_token_hash: str = Field(nullable=False, index=True, unique=True)
    device_id: str = Field(nullable=False, index=True)
    user_agent: str | None = Field(default=None, sa_type=Text(), nullable=True)
    ip_address: str | None = Field(default=None, nullable=True)
    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    last_seen_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )


class UserBudgetDailyModel(BaseModel, table=True):
    """User daily budget database model."""

    __tablename__ = "user_budget_daily"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_budget_daily_user_date"),
    )

    user_id: str = Field(nullable=False, index=True)
    date: str = Field(nullable=False, index=True)
    embedding_tokens_est: int = Field(default=0, nullable=False)
    judge_tokens_est: int = Field(default=0, nullable=False)
    usd_est: float = Field(default=0.0, nullable=False)
