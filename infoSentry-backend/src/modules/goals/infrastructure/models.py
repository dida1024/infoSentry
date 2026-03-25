"""Goal database models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Enum
from sqlmodel import Field, SQLModel

from src.core.infrastructure.database.base_model import BaseModel
from src.modules.goals.domain.entities import GoalStatus, PriorityMode, TermType


def _utc_now() -> datetime:
    return datetime.now(UTC)


class GoalModel(BaseModel, table=True):
    """Goal database model."""

    __tablename__ = "goals"

    user_id: str = Field(nullable=False, index=True)
    name: str = Field(nullable=False)
    description: str = Field(nullable=False)
    status: GoalStatus = Field(
        default=GoalStatus.ACTIVE,
        sa_column=Column(
            Enum(
                GoalStatus,
                name="goalstatus",
                values_callable=lambda e: [i.value for i in e],
                create_constraint=False,
            ),
            nullable=False,
            index=True,
        ),
    )
    priority_mode: PriorityMode = Field(
        default=PriorityMode.SOFT,
        sa_column=Column(
            Enum(
                PriorityMode,
                name="prioritymode",
                values_callable=lambda e: [i.value for i in e],
                create_constraint=False,
            ),
            nullable=False,
        ),
    )
    time_window_days: int = Field(default=7, nullable=False)


class GoalPushConfigModel(SQLModel, table=True):
    """Goal push configuration database model."""

    __tablename__ = "goal_push_configs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    is_deleted: bool = Field(default=False, nullable=False)

    goal_id: str = Field(nullable=False, index=True, unique=True)
    batch_windows: list[str] = Field(
        default_factory=lambda: ["12:30", "18:30"],
        sa_type=JSON,
        nullable=False,
    )
    digest_send_time: str = Field(default="09:00", nullable=False)
    immediate_enabled: bool = Field(default=True, nullable=False)
    batch_enabled: bool = Field(default=True, nullable=False)
    digest_enabled: bool = Field(default=True, nullable=False)


class GoalPriorityTermModel(SQLModel, table=True):
    """Goal priority term database model."""

    __tablename__ = "goal_priority_terms"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    is_deleted: bool = Field(default=False, nullable=False)

    goal_id: str = Field(nullable=False, index=True)
    term: str = Field(nullable=False)
    term_type: TermType = Field(
        default=TermType.MUST,
        sa_column=Column(
            Enum(
                TermType,
                name="termtype",
                values_callable=lambda e: [i.value for i in e],
                create_constraint=False,
            ),
            nullable=False,
        ),
    )
