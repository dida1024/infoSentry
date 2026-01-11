"""统一的健康检查类型定义。

所有基础设施组件的健康检查都使用这些类型，确保类型安全和一致性。
"""

from enum import Enum

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """健康检查状态枚举。"""

    OK = "ok"
    ERROR = "error"
    SKIPPED = "skipped"
    DEGRADED = "degraded"


class DatabaseHealthResult(BaseModel):
    """数据库健康检查结果。"""

    status: HealthStatus = Field(..., description="健康状态")
    connected: bool = Field(..., description="是否已连接")
    version: str | None = Field(None, description="PostgreSQL 版本")
    pgvector: bool = Field(False, description="pgvector 扩展是否可用")
    error: str | None = Field(None, description="错误信息")

    def to_dict(self) -> dict[str, str | bool | None]:
        """转换为字典（用于 API 响应）。"""
        return self.model_dump(mode="json", exclude_none=False)


class RedisHealthResult(BaseModel):
    """Redis 健康检查结果。"""

    status: HealthStatus = Field(..., description="健康状态")
    connected: bool = Field(..., description="是否已连接")
    version: str | None = Field(None, description="Redis 版本")
    error: str | None = Field(None, description="错误信息")

    def to_dict(self) -> dict[str, str | bool | None]:
        """转换为字典（用于 API 响应）。"""
        return self.model_dump(mode="json", exclude_none=False)


class EmailHealthResult(BaseModel):
    """邮件服务健康检查结果。"""

    available: bool = Field(..., description="邮件服务是否可用")
    circuit_open: bool = Field(..., description="熔断器是否开启")
    consecutive_failures: int = Field(..., description="连续失败次数")
    smtp_configured: bool = Field(..., description="SMTP 是否已配置")
    email_enabled: bool = Field(..., description="邮件功能是否启用")

    def to_dict(self) -> dict[str, bool | int]:
        """转换为字典（用于 API 响应）。"""
        return self.model_dump(mode="json")
