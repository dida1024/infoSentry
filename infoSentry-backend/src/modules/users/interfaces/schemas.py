"""User API schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RequestMagicLinkRequest(BaseModel):
    """Request magic link."""

    email: EmailStr = Field(..., description="邮箱地址")

    class Config:
        json_schema_extra = {"example": {"email": "user@example.com"}}


class MagicLinkResponse(BaseModel):
    """Magic link response."""

    ok: bool = True
    message: str = "登录链接已发送到邮箱"


class SessionResponse(BaseModel):
    """Session info after successful login."""

    user_id: str = Field(..., description="用户ID")
    email: EmailStr = Field(..., description="用户邮箱")
    access_token: str = Field(..., description="JWT访问令牌")
    expires_at: datetime = Field(..., description="令牌过期时间")


class ConsumeTokenResponse(BaseModel):
    """Response after consuming magic link."""

    ok: bool = True
    session: SessionResponse


class UserResponse(BaseModel):
    """User info response."""

    id: str = Field(..., description="用户ID")
    email: EmailStr = Field(..., description="邮箱")
    is_active: bool = Field(..., description="是否激活")
    status: str = Field(..., description="状态")
    display_name: str | None = Field(None, description="显示名称")
    timezone: str = Field(..., description="时区")
    last_login_at: datetime | None = Field(None, description="最后登录时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    """Update user profile request."""

    display_name: str | None = Field(None, max_length=100, description="显示名称")
    timezone: str | None = Field(None, description="时区")

    class Config:
        json_schema_extra = {
            "example": {"display_name": "张三", "timezone": "Asia/Shanghai"}
        }


class UserBudgetUsageDay(BaseModel):
    """User daily budget usage."""

    date: str = Field(..., description="日期")
    embedding_tokens_est: int = Field(..., description="embedding token估算")
    judge_tokens_est: int = Field(..., description="judge token估算")
    usd_est: float = Field(..., description="美元估算")
    daily_limit: float = Field(..., description="每日预算上限")
    usage_percent: float = Field(..., description="当日使用百分比")


class UserBudgetUsageResponse(BaseModel):
    """User budget usage response."""

    user_id: str = Field(..., description="用户ID")
    start_date: str = Field(..., description="起始日期")
    end_date: str = Field(..., description="结束日期")
    total_embedding_tokens_est: int = Field(..., description="embedding token总估算")
    total_judge_tokens_est: int = Field(..., description="judge token总估算")
    total_usd_est: float = Field(..., description="美元总估算")
    daily_limit: float = Field(..., description="每日预算上限")
    days: list[UserBudgetUsageDay] = Field(..., description="按日统计")
