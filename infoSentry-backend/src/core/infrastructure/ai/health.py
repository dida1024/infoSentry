"""AI 服务健康检查。

提供 OpenAI API 的可用性检查，包括：
- 网络连通性
- API 认证状态
- 服务响应能力
"""

import time

from loguru import logger
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.infrastructure.health import HealthStatus


class AIServiceHealthResult(BaseModel):
    """AI 服务健康检查结果。"""

    status: HealthStatus = Field(..., description="健康状态")
    message: str | None = Field(None, description="状态消息")
    base_url: str | None = Field(None, description="API 基础 URL")
    latency_ms: int | None = Field(None, description="延迟（毫秒）", ge=0)
    models_available: int | None = Field(None, description="可用模型数量", ge=0)
    sample_models: list[str] | None = Field(None, description="示例模型列表（最多5个）")
    error: str | None = Field(None, description="错误信息")

    def to_dict(self) -> dict[str, str | int | list[str] | None]:
        """转换为字典（用于 API 响应）。"""
        return self.model_dump(mode="json", exclude_none=False)


async def check_ai_service_health() -> AIServiceHealthResult:
    """检查 AI 服务（OpenAI API）的健康状态。

    执行轻量级的 API 调用以验证：
    1. 网络可达性
    2. API Key 有效性
    3. 服务可用性

    Returns:
        AIServiceHealthResult: 健康检查结果
    """
    # 如果 AI 功能未启用，直接返回跳过状态
    if not settings.LLM_ENABLED and not settings.EMBEDDING_ENABLED:
        return AIServiceHealthResult(
            status=HealthStatus.SKIPPED,
            message="AI features are disabled",
        )

    # 检查 API Key 配置
    if not settings.OPENAI_API_KEY:
        logger.warning("OpenAI API key is not configured")
        return AIServiceHealthResult(
            status=HealthStatus.ERROR,
            error="API key not configured",
        )

    try:
        # 创建客户端
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE,
            timeout=5.0,  # 5 秒超时
        )

        # 使用 models.list() 进行健康检查（轻量级操作）
        start_time = time.time()
        models = await client.models.list()
        latency_ms = int((time.time() - start_time) * 1000)

        # 获取可用模型列表
        model_ids = [model.id for model in models.data[:5]]  # 只取前 5 个

        logger.info(
            "OpenAI API health check passed",
            latency_ms=latency_ms,
            model_count=len(models.data),
        )

        return AIServiceHealthResult(
            status=HealthStatus.OK,
            base_url=settings.OPENAI_API_BASE,
            latency_ms=latency_ms,
            models_available=len(models.data),
            sample_models=model_ids,
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(
            "OpenAI API health check failed",
            error=error_msg,
            base_url=settings.OPENAI_API_BASE,
        )

        return AIServiceHealthResult(
            status=HealthStatus.ERROR,
            error=error_msg,
            base_url=settings.OPENAI_API_BASE,
        )
