"""Goal API schemas."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class GoalStatus(str, Enum):
    """Goal status enum for API layer."""

    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class PriorityMode(str, Enum):
    """Priority mode for API layer."""

    STRICT = "STRICT"
    SOFT = "SOFT"


class CreateGoalRequest(BaseModel):
    """Create goal request."""

    name: str = Field(..., min_length=1, max_length=100, description="目标名称")
    description: str = Field(..., min_length=1, description="目标描述")
    priority_mode: PriorityMode = Field(
        default=PriorityMode.SOFT, description="优先模式"
    )
    priority_terms: list[str] | None = Field(None, description="优先词条（多行）")
    negative_terms: list[str] | None = Field(None, description="负面词条")
    batch_enabled: bool | None = Field(None, description="是否启用批量推送")
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
                "batch_enabled": True,
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
    batch_enabled: bool | None = Field(None, description="是否启用批量推送")
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
    batch_enabled: bool = Field(..., description="是否启用批量推送")
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


class ItemResponse(BaseModel):
    """Item response for match results."""

    id: str = Field(..., description="Item ID")
    url: str = Field(..., description="原文URL")
    title: str = Field(..., description="标题")
    snippet: str | None = Field(None, description="摘要片段")
    summary: str | None = Field(None, description="AI生成的摘要")
    published_at: datetime | None = Field(None, description="发布时间")
    ingested_at: datetime = Field(..., description="入库时间")
    source_name: str | None = Field(None, description="来源名称")

    class Config:
        from_attributes = True


class GoalItemMatchResponse(BaseModel):
    """Goal-Item match response."""

    id: str = Field(..., description="Match ID")
    goal_id: str = Field(..., description="Goal ID")
    item_id: str = Field(..., description="Item ID")
    match_score: float = Field(..., description="匹配分数")
    features_json: dict = Field(default_factory=dict, description="特征值")
    reasons_json: dict = Field(default_factory=dict, description="匹配原因")
    computed_at: datetime = Field(..., description="计算时间")
    item: ItemResponse | None = Field(None, description="关联的Item")

    class Config:
        from_attributes = True


class SuggestKeywordsRequest(BaseModel):
    """关键词建议请求。"""

    description: str = Field(
        ..., min_length=10, max_length=2000, description="目标描述"
    )
    max_keywords: int = Field(5, ge=1, le=10, description="最大关键词数量")

    class Config:
        json_schema_extra = {
            "example": {
                "description": "追踪 AI 领域的重要新闻和技术突破，包括大语言模型、AI 芯片、自动驾驶等方向",
                "max_keywords": 5,
            }
        }


class SuggestKeywordsResponse(BaseModel):
    """关键词建议响应。"""

    keywords: list[str] = Field(..., description="建议的关键词列表")


class GenerateGoalDraftRequest(BaseModel):
    """目标草稿生成请求。"""

    intent: str = Field(
        ...,
        min_length=3,
        max_length=300,
        description="用户意图（想关注什么）",
    )
    max_keywords: int = Field(5, ge=1, le=10, description="最大关键词数量")

    class Config:
        json_schema_extra = {
            "example": {
                "intent": "关注 AI 行业投融资、模型发布和监管政策，优先看头部公司动态",
                "max_keywords": 5,
            }
        }


class GenerateGoalDraftResponse(BaseModel):
    """目标草稿生成响应。"""

    name: str = Field(..., description="建议的目标名称")
    description: str = Field(..., description="建议的目标描述")
    keywords: list[str] = Field(default_factory=list, description="建议关键词列表")


class SendGoalEmailRequest(BaseModel):
    """立即发送目标推送邮件请求。"""

    since: datetime | None = Field(
        None,
        description="只包含此时间后匹配的项目（默认24小时前）",
    )
    min_score: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="最低匹配分数过滤",
    )
    limit: int = Field(
        20,
        ge=1,
        le=50,
        description="最大项目数",
    )
    include_sent: bool = Field(
        False,
        description="是否包含已发送的项目",
    )
    dry_run: bool = Field(
        False,
        description="预览模式，不实际发送",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "min_score": 0.6,
                "limit": 20,
                "include_sent": False,
                "dry_run": False,
            }
        }


class EmailPreviewData(BaseModel):
    """邮件预览数据。"""

    subject: str = Field(..., description="邮件主题")
    to_email: str = Field(..., description="收件人邮箱")
    item_titles: list[str] = Field(..., description="包含的项目标题列表")


class SendGoalEmailResponse(BaseModel):
    """立即发送目标推送邮件响应。"""

    success: bool = Field(..., description="操作是否成功")
    email_sent: bool = Field(..., description="邮件是否实际发送")
    items_count: int = Field(..., description="包含的项目数")
    decisions_updated: int = Field(..., description="更新的推送决策数")
    preview: EmailPreviewData | None = Field(
        None,
        description="邮件预览（dry_run=true 时返回）",
    )
    message: str = Field(..., description="结果消息")
