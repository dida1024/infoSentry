"""Goal API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.modules.goals.domain.entities import GoalStatus, PriorityMode


class CreateGoalRequest(BaseModel):
    """Create goal request."""

    name: str = Field(..., min_length=1, max_length=100, description="目标名称")
    description: str = Field(..., min_length=1, description="目标描述")
    priority_mode: PriorityMode = Field(
        default=PriorityMode.SOFT, description="优先模式"
    )
    priority_terms: list[str] | None = Field(None, description="优先词条（多行）")
    negative_terms: list[str] | None = Field(None, description="负面词条")
    batch_windows: list[str] | None = Field(None, description="批量推送窗口（HH:MM）")
    digest_send_time: str | None = Field(None, description="每日摘要时间（HH:MM）")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "AI 行业动态",
                "description": "追踪 AI 领域的重要新闻和技术突破",
                "priority_mode": "STRICT",
                "priority_terms": ["GPT", "Claude", "LLM", "大模型"],
                "negative_terms": ["广告", "招聘"],
                "batch_windows": ["12:30", "18:30"],
                "digest_send_time": "09:00",
            }
        }


class UpdateGoalRequest(BaseModel):
    """Update goal request."""

    name: str | None = Field(None, min_length=1, max_length=100, description="目标名称")
    description: str | None = Field(None, description="目标描述")
    priority_mode: PriorityMode | None = Field(None, description="优先模式")
    priority_terms: list[str] | None = Field(None, description="优先词条")
    negative_terms: list[str] | None = Field(None, description="负面词条")
    batch_windows: list[str] | None = Field(None, description="批量推送窗口")
    digest_send_time: str | None = Field(None, description="每日摘要时间")


class GoalStatsResponse(BaseModel):
    """Goal statistics."""

    total_matches: int = Field(default=0, description="总匹配数")
    immediate_count: int = Field(default=0, description="即时推送数")
    batch_count: int = Field(default=0, description="批量推送数")
    digest_count: int = Field(default=0, description="摘要推送数")


class GoalResponse(BaseModel):
    """Goal response."""

    id: str = Field(..., description="Goal ID")
    name: str = Field(..., description="名称")
    description: str = Field(..., description="描述")
    priority_mode: PriorityMode = Field(..., description="优先模式")
    status: GoalStatus = Field(..., description="状态")
    priority_terms: list[str] | None = Field(None, description="优先词条")
    negative_terms: list[str] | None = Field(None, description="负面词条")
    batch_windows: list[str] | None = Field(None, description="批量推送窗口")
    digest_send_time: str | None = Field(None, description="每日摘要时间")
    stats: GoalStatsResponse | None = Field(None, description="统计信息")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class GoalListResponse(BaseModel):
    """Goal list response."""

    goals: list[GoalResponse]


class GoalStatusResponse(BaseModel):
    """Goal status change response."""

    ok: bool = True
    status: GoalStatus
