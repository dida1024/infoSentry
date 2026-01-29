"""Goal application commands."""

from pydantic import BaseModel

from src.modules.goals.domain.entities import PriorityMode


class CreateGoalCommand(BaseModel):
    """Create a new goal."""

    user_id: str
    name: str
    description: str
    priority_mode: PriorityMode = PriorityMode.SOFT
    priority_terms: list[str] | None = None  # 优先词条
    negative_terms: list[str] | None = None  # 负面词条
    batch_enabled: bool | None = None  # 是否启用批量推送
    batch_windows: list[str] | None = None  # 批量推送窗口
    digest_send_time: str | None = None  # 每日摘要时间


class UpdateGoalCommand(BaseModel):
    """Update an existing goal."""

    goal_id: str
    user_id: str  # For access check
    name: str | None = None
    description: str | None = None
    priority_mode: PriorityMode | None = None
    priority_terms: list[str] | None = None
    negative_terms: list[str] | None = None
    batch_enabled: bool | None = None
    batch_windows: list[str] | None = None
    digest_send_time: str | None = None


class PauseGoalCommand(BaseModel):
    """Pause a goal."""

    goal_id: str
    user_id: str


class ResumeGoalCommand(BaseModel):
    """Resume a goal."""

    goal_id: str
    user_id: str


class ArchiveGoalCommand(BaseModel):
    """Archive a goal."""

    goal_id: str
    user_id: str


class DeleteGoalCommand(BaseModel):
    """Delete a goal (soft delete)."""

    goal_id: str
    user_id: str
