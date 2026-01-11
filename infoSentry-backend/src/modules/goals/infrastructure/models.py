"""Goal database models."""

from sqlalchemy import JSON, Enum
from sqlmodel import Field

from src.core.infrastructure.database.base_model import BaseModel
from src.modules.goals.domain.entities import GoalStatus, PriorityMode, TermType


class GoalModel(BaseModel, table=True):
    """Goal database model."""

    __tablename__ = "goals"

    user_id: str = Field(nullable=False, index=True)
    name: str = Field(nullable=False)
    description: str = Field(nullable=False)
    status: GoalStatus = Field(
        default=GoalStatus.ACTIVE,
        sa_type=Enum(
            GoalStatus,
            name="goalstatus",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
        index=True,
    )
    priority_mode: PriorityMode = Field(
        default=PriorityMode.SOFT,
        sa_type=Enum(
            PriorityMode,
            name="prioritymode",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
    )
    time_window_days: int = Field(default=7, nullable=False)


class GoalPushConfigModel(BaseModel, table=True):
    """Goal push configuration database model."""

    __tablename__ = "goal_push_configs"

    goal_id: str = Field(nullable=False, index=True, unique=True)
    batch_windows: list = Field(
        default_factory=lambda: ["12:30", "18:30"],
        sa_type=JSON,
        nullable=False,
    )
    digest_send_time: str = Field(default="09:00", nullable=False)
    immediate_enabled: bool = Field(default=True, nullable=False)
    batch_enabled: bool = Field(default=True, nullable=False)
    digest_enabled: bool = Field(default=True, nullable=False)


class GoalPriorityTermModel(BaseModel, table=True):
    """Goal priority term database model."""

    __tablename__ = "goal_priority_terms"

    goal_id: str = Field(nullable=False, index=True)
    term: str = Field(nullable=False)
    term_type: TermType = Field(
        default=TermType.MUST,
        sa_type=Enum(
            TermType,
            name="termtype",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
    )
