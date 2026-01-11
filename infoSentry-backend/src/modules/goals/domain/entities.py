"""Goal domain entities."""

from enum import Enum

from pydantic import Field

from src.core.domain.aggregate_root import AggregateRoot
from src.core.domain.base_entity import BaseEntity


class GoalStatus(str, Enum):
    """Goal status enum."""

    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class PriorityMode(str, Enum):
    """Priority mode for goal matching."""

    STRICT = "STRICT"  # 不命中 priority_terms 禁止 Immediate
    SOFT = "SOFT"  # priority_terms 作为偏好/加分，不强制


class TermType(str, Enum):
    """Term type enum."""

    MUST = "must"  # 优先词
    NEGATIVE = "negative"  # 负面词


class Goal(AggregateRoot):
    """Goal aggregate root - 追踪目标。"""

    user_id: str = Field(..., description="所属用户ID")
    name: str = Field(..., description="目标名称")
    description: str = Field(..., description="目标描述")
    status: GoalStatus = Field(default=GoalStatus.ACTIVE, description="目标状态")
    priority_mode: PriorityMode = Field(
        default=PriorityMode.SOFT, description="优先模式"
    )
    time_window_days: int = Field(default=7, description="时间窗口（天）")

    def pause(self) -> None:
        """Pause the goal."""
        if self.status == GoalStatus.PAUSED:
            return
        self.status = GoalStatus.PAUSED
        self._update_timestamp()

        from src.modules.goals.domain.events import GoalPausedEvent

        self.add_domain_event(GoalPausedEvent(goal_id=self.id, name=self.name))

    def resume(self) -> None:
        """Resume the goal."""
        if self.status == GoalStatus.ACTIVE:
            return
        self.status = GoalStatus.ACTIVE
        self._update_timestamp()

        from src.modules.goals.domain.events import GoalResumedEvent

        self.add_domain_event(GoalResumedEvent(goal_id=self.id, name=self.name))

    def archive(self) -> None:
        """Archive the goal."""
        if self.status == GoalStatus.ARCHIVED:
            return
        self.status = GoalStatus.ARCHIVED
        self._update_timestamp()

        from src.modules.goals.domain.events import GoalArchivedEvent

        self.add_domain_event(GoalArchivedEvent(goal_id=self.id, name=self.name))

    def update_info(
        self,
        name: str | None = None,
        description: str | None = None,
        priority_mode: PriorityMode | None = None,
    ) -> list[str]:
        """Update goal info."""
        updated_fields: list[str] = []

        if name is not None and name != self.name:
            self.name = name
            updated_fields.append("name")

        if description is not None and description != self.description:
            self.description = description
            updated_fields.append("description")

        if priority_mode is not None and priority_mode != self.priority_mode:
            self.priority_mode = priority_mode
            updated_fields.append("priority_mode")

        if updated_fields:
            self._update_timestamp()
            from src.modules.goals.domain.events import GoalUpdatedEvent

            self.add_domain_event(
                GoalUpdatedEvent(
                    goal_id=self.id,
                    name=self.name,
                    updated_fields=updated_fields,
                )
            )

        return updated_fields

    def is_active(self) -> bool:
        """Check if goal is active."""
        return self.status == GoalStatus.ACTIVE


class GoalPushConfig(BaseEntity):
    """Goal push configuration - 推送配置。"""

    goal_id: str = Field(..., description="关联的Goal ID")
    batch_windows: list[str] = Field(
        default_factory=lambda: ["12:30", "18:30"],
        description="批量推送窗口时间（HH:MM格式）",
    )
    digest_send_time: str = Field(
        default="09:00", description="每日摘要发送时间（HH:MM格式）"
    )
    immediate_enabled: bool = Field(default=True, description="是否启用即时推送")
    batch_enabled: bool = Field(default=True, description="是否启用批量推送")
    digest_enabled: bool = Field(default=True, description="是否启用每日摘要")

    def update_windows(self, windows: list[str]) -> None:
        """Update batch windows."""
        # 最多3个窗口
        self.batch_windows = windows[:3]
        self._update_timestamp()

    def update_digest_time(self, time: str) -> None:
        """Update digest send time."""
        self.digest_send_time = time
        self._update_timestamp()


class GoalPriorityTerm(BaseEntity):
    """Goal priority term - 优先词条。"""

    goal_id: str = Field(..., description="关联的Goal ID")
    term: str = Field(..., description="词条内容")
    term_type: TermType = Field(default=TermType.MUST, description="词条类型")
