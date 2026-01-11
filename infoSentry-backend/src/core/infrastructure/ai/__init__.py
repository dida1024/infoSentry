"""AI 服务基础设施模块。"""

from .health import AIServiceHealthResult, check_ai_service_health

__all__ = ["check_ai_service_health", "AIServiceHealthResult"]
