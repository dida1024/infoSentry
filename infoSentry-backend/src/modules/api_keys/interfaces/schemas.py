"""API Key API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.modules.api_keys.domain.entities import ApiKeyScope


class CreateApiKeyRequest(BaseModel):
    """Create API key request."""

    name: str = Field(..., min_length=1, max_length=100, description="Key 名称")
    scopes: list[ApiKeyScope] = Field(..., min_length=1, description="授权 scope 列表")
    expires_in_days: int | None = Field(
        default=None, ge=1, le=3650, description="过期天数（不填则使用默认值）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "My GPT Agent",
                "scopes": ["goals:read", "goals:write", "sources:read"],
                "expires_in_days": 365,
            }
        }


class ApiKeyResponse(BaseModel):
    """API key response (without hash or raw key)."""

    id: str = Field(..., description="Key ID")
    name: str = Field(..., description="Key 名称")
    key_prefix: str = Field(..., description="Key 前缀（用于识别）")
    scopes: list[str] = Field(..., description="授权 scope 列表")
    is_active: bool = Field(..., description="是否激活")
    expires_at: datetime | None = Field(None, description="过期时间")
    last_used_at: datetime | None = Field(None, description="最后使用时间")
    created_at: datetime = Field(..., description="创建时间")


class ApiKeyCreatedResponse(BaseModel):
    """Response after creating an API key (includes raw key)."""

    key: ApiKeyResponse = Field(..., description="Key 信息")
    raw_key: str = Field(
        ...,
        description="API Key 明文（仅此一次展示，请立即复制保存）",
    )


class ApiKeyListResponse(BaseModel):
    """API key list response."""

    keys: list[ApiKeyResponse] = Field(..., description="Key 列表")
    total: int = Field(..., description="总数")
