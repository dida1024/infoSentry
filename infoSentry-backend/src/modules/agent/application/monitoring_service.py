"""监控与告警服务。

目标：
- LLM/SMTP/队列监控及阈值告警
- 降级开关检查
- 健康状态汇总
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.domain.ports.kv import KVClient


class WorkerHeartbeat(BaseModel):
    """单个 Worker 心跳状态。"""

    status: str = Field(..., description="Worker 状态 (ok/stale/unknown/error)")
    last_heartbeat: str | None = Field(None, description="最后心跳时间 (ISO格式)")
    age_seconds: int | None = Field(None, description="心跳年龄（秒）", ge=0)
    error: str | None = Field(None, description="错误信息")

    def to_dict(self) -> dict[str, str | int | None]:
        """转换为字典（用于 API 响应）。"""
        return self.model_dump(mode="json", exclude_none=False)


class WorkerHeartbeatResult(BaseModel):
    """Worker 心跳状态汇总结果。"""

    workers: dict[str, WorkerHeartbeat] = Field(
        default_factory=dict, description="各 Worker 的心跳状态"
    )

    def to_dict(self) -> dict[str, dict[str, str | int | None]]:
        """转换为字典（用于 API 响应）。"""
        return {
            worker_type: heartbeat.to_dict()
            for worker_type, heartbeat in self.workers.items()
        }


class AlertLevel(str, Enum):
    """告警级别。"""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Alert:
    """告警记录。"""

    level: AlertLevel
    source: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "source": self.source,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class HealthStatus:
    """健康状态。"""

    healthy: bool = True
    status: str = "healthy"
    components: dict[str, dict[str, Any]] = field(default_factory=dict)
    alerts: list[Alert] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "status": self.status,
            "components": self.components,
            "alerts": [a.to_dict() for a in self.alerts],
            "timestamp": self.timestamp.isoformat(),
        }


class MonitoringService:
    """监控服务。

    职责：
    - 检查队列积压
    - 检查 LLM 调用错误率
    - 检查 SMTP 连接状态
    - 生成告警
    - 自动降级
    """

    # Redis keys
    LLM_ERROR_COUNT_KEY = "monitor:llm:errors"
    SMTP_ERROR_STREAK_KEY = "monitor:smtp:error_streak"
    LAST_HEALTH_CHECK_KEY = "monitor:health:last_check"

    def __init__(self, redis_client: KVClient):
        self.redis = redis_client

    async def check_all(self) -> HealthStatus:
        """执行所有健康检查。"""
        status = HealthStatus()

        # 检查队列
        await self._check_queues(status)

        # 检查 LLM 错误率
        await self._check_llm_errors(status)

        # 检查 SMTP 状态
        await self._check_smtp_status(status)

        # 检查降级开关状态
        await self._check_feature_flags(status)

        # 检查预算状态
        await self._check_budget(status)

        # 更新最后检查时间
        await self.redis.set(
            self.LAST_HEALTH_CHECK_KEY,
            datetime.now(UTC).isoformat(),
            ex=3600,
        )

        # 确定整体状态
        if any(a.level == AlertLevel.CRITICAL for a in status.alerts):
            status.healthy = False
            status.status = "critical"
        elif any(a.level == AlertLevel.WARNING for a in status.alerts):
            status.status = "degraded"

        return status

    async def _check_queues(self, status: HealthStatus) -> None:
        """检查 Celery 队列积压。"""
        from src.core.domain.queues import Queues

        queues = [
            Queues.INGEST,
            Queues.EMBED,
            Queues.MATCH,
            Queues.AGENT,
            Queues.EMAIL,
        ]

        queue_status = {}
        for queue in queues:
            try:
                # 通过 Redis LIST 长度检查队列积压
                # Celery 使用 Redis 时，队列名作为 LIST key
                length = await self.redis.llen(queue)
                queue_status[queue] = {
                    "length": length,
                    "status": "ok",
                }

                if length >= settings.QUEUE_BACKLOG_CRITICAL:
                    queue_status[queue]["status"] = "critical"
                    status.alerts.append(
                        Alert(
                            level=AlertLevel.CRITICAL,
                            source="queue",
                            message=f"Queue {queue} has critical backlog",
                            details={"queue": queue, "length": length},
                        )
                    )
                    logger.error(f"Critical queue backlog: {queue}={length}")

                elif length >= settings.QUEUE_BACKLOG_WARNING:
                    queue_status[queue]["status"] = "warning"
                    status.alerts.append(
                        Alert(
                            level=AlertLevel.WARNING,
                            source="queue",
                            message=f"Queue {queue} has backlog",
                            details={"queue": queue, "length": length},
                        )
                    )
                    logger.warning(f"Queue backlog warning: {queue}={length}")

            except Exception as e:
                queue_status[queue] = {
                    "length": -1,
                    "status": "error",
                    "error": str(e),
                }

        status.components["queues"] = queue_status

    async def _check_llm_errors(self, status: HealthStatus) -> None:
        """检查 LLM 调用错误率。"""
        # 获取当前小时的错误计数
        current_hour = datetime.now(UTC).strftime("%Y%m%d%H")
        error_key = f"{self.LLM_ERROR_COUNT_KEY}:{current_hour}"

        error_count = 0
        try:
            count_str = await self.redis.get(error_key)
            error_count = int(count_str) if count_str else 0
        except Exception as e:
            logger.warning(f"Failed to get LLM error count from Redis: {e}")

        llm_status = {
            "error_count_hour": error_count,
            "status": "ok",
            "llm_enabled": settings.LLM_ENABLED,
        }

        if error_count >= settings.LLM_ERROR_RATE_CRITICAL:
            llm_status["status"] = "critical"
            status.alerts.append(
                Alert(
                    level=AlertLevel.CRITICAL,
                    source="llm",
                    message=f"LLM error rate critical: {error_count}/hour",
                    details={
                        "error_count": error_count,
                        "threshold": settings.LLM_ERROR_RATE_CRITICAL,
                    },
                )
            )
            # 自动降级：禁用 LLM
            await self._auto_disable_llm()
            logger.error(
                f"LLM auto-disabled due to high error rate: {error_count}/hour"
            )

        elif error_count >= settings.LLM_ERROR_RATE_WARNING:
            llm_status["status"] = "warning"
            status.alerts.append(
                Alert(
                    level=AlertLevel.WARNING,
                    source="llm",
                    message=f"LLM error rate elevated: {error_count}/hour",
                    details={
                        "error_count": error_count,
                        "threshold": settings.LLM_ERROR_RATE_WARNING,
                    },
                )
            )
            logger.warning(f"LLM error rate warning: {error_count}/hour")

        status.components["llm"] = llm_status

    async def _check_smtp_status(self, status: HealthStatus) -> None:
        """检查 SMTP 连接状态。"""
        error_streak = 0
        try:
            streak_str = await self.redis.get(self.SMTP_ERROR_STREAK_KEY)
            error_streak = int(streak_str) if streak_str else 0
        except Exception as e:
            logger.warning(f"Failed to get SMTP error streak from Redis: {e}")

        smtp_status = {
            "error_streak": error_streak,
            "status": "ok",
            "email_enabled": settings.EMAIL_ENABLED,
            "smtp_configured": bool(settings.SMTP_HOST),
        }

        if error_streak >= settings.SMTP_ERROR_STREAK_CRITICAL:
            smtp_status["status"] = "critical"
            status.alerts.append(
                Alert(
                    level=AlertLevel.CRITICAL,
                    source="smtp",
                    message=f"SMTP connection failed {error_streak} times consecutively",
                    details={"error_streak": error_streak},
                )
            )
            # 自动降级：禁用邮件
            await self._auto_disable_email()
            logger.error(f"Email auto-disabled due to SMTP failures: {error_streak}")

        elif error_streak >= settings.SMTP_ERROR_STREAK_WARNING:
            smtp_status["status"] = "warning"
            status.alerts.append(
                Alert(
                    level=AlertLevel.WARNING,
                    source="smtp",
                    message=f"SMTP connection unstable: {error_streak} consecutive failures",
                    details={"error_streak": error_streak},
                )
            )
            logger.warning(f"SMTP error streak warning: {error_streak}")

        status.components["smtp"] = smtp_status

    async def _check_feature_flags(self, status: HealthStatus) -> None:
        """检查降级开关状态。"""
        flags = {
            "LLM_ENABLED": settings.LLM_ENABLED,
            "EMBEDDING_ENABLED": settings.EMBEDDING_ENABLED,
            "IMMEDIATE_ENABLED": settings.IMMEDIATE_ENABLED,
            "EMAIL_ENABLED": settings.EMAIL_ENABLED,
        }

        # 检查 Redis 中的动态配置覆盖
        for key in flags:
            try:
                redis_value = await self.redis.get(f"config:{key}")
                if redis_value is not None:
                    flags[f"{key}_override"] = redis_value.lower() == "true"
            except Exception as e:
                logger.debug(f"Failed to get config override for {key}: {e}")

        status.components["feature_flags"] = flags

        # 如果有降级，添加信息告警
        disabled_flags = [
            k for k, v in flags.items() if not v and not k.endswith("_override")
        ]
        if disabled_flags:
            status.alerts.append(
                Alert(
                    level=AlertLevel.INFO,
                    source="feature_flags",
                    message=f"Features disabled: {', '.join(disabled_flags)}",
                    details={"disabled": disabled_flags},
                )
            )

    async def _check_budget(self, status: HealthStatus) -> None:
        """检查预算状态。"""
        from src.modules.items.application.budget_service import BudgetService

        budget_service = BudgetService(self.redis)
        budget_status = await budget_service.get_status()

        budget_info = {
            "date": budget_status.date,
            "usd_est": round(budget_status.usd_est, 4),
            "daily_limit": settings.DAILY_USD_BUDGET,
            "usage_percent": round(
                budget_status.usd_est / settings.DAILY_USD_BUDGET * 100, 1
            ),
            "embedding_disabled": budget_status.embedding_disabled,
            "judge_disabled": budget_status.judge_disabled,
        }

        status.components["budget"] = budget_info

        # 检查是否接近预算上限
        usage_percent = budget_info["usage_percent"]
        if usage_percent >= 100:
            status.alerts.append(
                Alert(
                    level=AlertLevel.WARNING,
                    source="budget",
                    message="Daily budget exhausted",
                    details=budget_info,
                )
            )
        elif usage_percent >= 80:
            status.alerts.append(
                Alert(
                    level=AlertLevel.INFO,
                    source="budget",
                    message=f"Daily budget usage at {usage_percent}%",
                    details=budget_info,
                )
            )

    async def _auto_disable_llm(self) -> None:
        """自动禁用 LLM（降级）。"""
        await self.redis.set("config:LLM_ENABLED", "false")
        logger.warning("LLM auto-disabled via config override")

    async def _auto_disable_email(self) -> None:
        """自动禁用邮件（降级）。"""
        await self.redis.set("config:EMAIL_ENABLED", "false")
        logger.warning("Email auto-disabled via config override")

    async def record_llm_error(self) -> int:
        """记录 LLM 调用错误。

        Returns:
            当前小时的错误计数
        """
        current_hour = datetime.now(UTC).strftime("%Y%m%d%H")
        error_key = f"{self.LLM_ERROR_COUNT_KEY}:{current_hour}"

        count = await self.redis.incr(error_key)
        # 设置 2 小时过期
        await self.redis.expire(error_key, 7200)

        logger.debug(f"LLM error recorded, count this hour: {count}")
        return count

    async def record_smtp_error(self) -> int:
        """记录 SMTP 发送错误。

        Returns:
            连续错误次数
        """
        count = await self.redis.incr(self.SMTP_ERROR_STREAK_KEY)
        # 设置 24 小时过期
        await self.redis.expire(self.SMTP_ERROR_STREAK_KEY, 86400)

        logger.debug(f"SMTP error recorded, streak: {count}")
        return count

    async def reset_smtp_error_streak(self) -> None:
        """重置 SMTP 错误计数（成功发送后调用）。"""
        await self.redis.delete(self.SMTP_ERROR_STREAK_KEY)
        logger.debug("SMTP error streak reset")

    async def get_worker_heartbeats(self) -> WorkerHeartbeatResult:
        """获取 Worker 心跳状态。"""
        # 检查各个 Worker 的心跳 key
        result = WorkerHeartbeatResult()
        worker_types = ["ingest", "embed", "match", "agent", "email"]

        for worker_type in worker_types:
            heartbeat_key = f"worker:heartbeat:{worker_type}"
            try:
                last_beat = await self.redis.get(heartbeat_key)
                if last_beat:
                    last_beat_time = datetime.fromisoformat(last_beat)
                    age_seconds = (datetime.now(UTC) - last_beat_time).total_seconds()
                    result.workers[worker_type] = WorkerHeartbeat(
                        status="ok"
                        if age_seconds < settings.WORKER_HEARTBEAT_STALE_SEC
                        else "stale",
                        last_heartbeat=last_beat,
                        age_seconds=int(age_seconds),
                    )
                else:
                    result.workers[worker_type] = WorkerHeartbeat(
                        status="unknown",
                        last_heartbeat=None,
                    )
            except Exception as e:
                result.workers[worker_type] = WorkerHeartbeat(
                    status="error",
                    error=str(e),
                )

        return result

    async def record_worker_heartbeat(self, worker_type: str) -> None:
        """记录 Worker 心跳。

        Args:
            worker_type: Worker 类型（ingest/embed/match/agent/email）
        """
        heartbeat_key = f"worker:heartbeat:{worker_type}"
        await self.redis.set(
            heartbeat_key,
            datetime.now(UTC).isoformat(),
            ex=settings.WORKER_HEARTBEAT_TTL_SEC,
        )
