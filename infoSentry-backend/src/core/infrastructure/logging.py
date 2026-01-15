"""Logging configuration with structlog integration.

提供两种日志记录方式：
1. loguru: 用于一般调试日志
2. structlog: 用于关键业务事件的结构化日志
"""

import sys
from typing import Any

import structlog
from loguru import logger

from src.core.config import settings


def setup_logging() -> None:
    """Configure application logging with structlog and loguru."""
    # 配置 structlog
    _configure_structlog()

    # 配置 loguru
    _configure_loguru()

    logger.info(f"Logging configured with level: {settings.LOG_LEVEL}")


def _configure_structlog() -> None:
    """配置 structlog 处理器链。"""
    # 根据环境选择渲染器
    if settings.ENVIRONMENT == "local":
        # 本地开发使用人类可读格式
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # 生产环境使用 JSON 格式
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            # 添加上下文变量
            structlog.contextvars.merge_contextvars,
            # 添加日志级别
            structlog.stdlib.add_log_level,
            # 添加时间戳
            structlog.processors.TimeStamper(fmt="iso"),
            # 添加调用者信息
            structlog.processors.CallsiteParameterAdder(
                [
                    structlog.processors.CallsiteParameter.MODULE,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),
            # 格式化异常
            structlog.processors.format_exc_info,
            # 最终渲染
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            _get_log_level_number(settings.LOG_LEVEL)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def _configure_loguru() -> None:
    """配置 loguru。"""
    # Remove default handler
    logger.remove()

    # Add console handler with appropriate level
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # Add file handler for production
    if settings.ENVIRONMENT != "local":
        logger.add(
            "logs/infosentry_{time:YYYY-MM-DD}.log",
            rotation="00:00",
            retention="30 days",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        )


def _get_log_level_number(level: str) -> int:
    """将日志级别字符串转换为数字。"""
    levels = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50,
    }
    return levels.get(level.upper(), 20)


# ============================================================================
# 业务事件日志记录器
# ============================================================================

def get_business_logger() -> structlog.BoundLogger:
    """获取业务事件日志记录器。

    用于记录关键业务事件，输出为结构化格式。

    Usage:
        from src.core.infrastructure.logging import get_business_logger

        log = get_business_logger()
        log.info("item_embedded", item_id="123", tokens=500, cost_usd=0.001)
    """
    return structlog.get_logger("business")


class BusinessEvents:
    """业务事件日志助手类。

    提供统一的业务事件日志记录接口，确保事件格式一致。

    Usage:
        from src.core.infrastructure.logging import BusinessEvents

        BusinessEvents.item_ingested(source_id="src_123", item_id="item_456", url="...")
        BusinessEvents.item_embedded(item_id="item_456", tokens_used=500)
    """

    _log = structlog.get_logger("business.events")

    @classmethod
    def item_ingested(
        cls,
        source_id: str,
        item_id: str,
        url: str,
        **extra: Any,
    ) -> None:
        """记录 Item 抓取事件。"""
        cls._log.info(
            "item_ingested",
            event_type="ingest",
            source_id=source_id,
            item_id=item_id,
            url=url,
            **extra,
        )

    @classmethod
    def item_embedded(
        cls,
        item_id: str,
        tokens_used: int,
        model: str | None = None,
        **extra: Any,
    ) -> None:
        """记录 Item 嵌入事件。"""
        cls._log.info(
            "item_embedded",
            event_type="embed",
            item_id=item_id,
            tokens_used=tokens_used,
            model=model,
            **extra,
        )

    @classmethod
    def item_matched(
        cls,
        item_id: str,
        goal_id: str,
        score: float,
        decision: str,
        **extra: Any,
    ) -> None:
        """记录 Item 匹配事件。"""
        cls._log.info(
            "item_matched",
            event_type="match",
            item_id=item_id,
            goal_id=goal_id,
            score=round(score, 4),
            decision=decision,
            **extra,
        )

    @classmethod
    def push_sent(
        cls,
        goal_id: str,
        channel: str,
        item_count: int,
        push_type: str,
        **extra: Any,
    ) -> None:
        """记录推送发送事件。"""
        cls._log.info(
            "push_sent",
            event_type="push",
            goal_id=goal_id,
            channel=channel,
            item_count=item_count,
            push_type=push_type,
            **extra,
        )

    @classmethod
    def agent_run_completed(
        cls,
        run_id: str,
        goal_id: str,
        item_id: str,
        action_count: int,
        latency_ms: int,
        **extra: Any,
    ) -> None:
        """记录 Agent 运行完成事件。"""
        cls._log.info(
            "agent_run_completed",
            event_type="agent",
            run_id=run_id,
            goal_id=goal_id,
            item_id=item_id,
            action_count=action_count,
            latency_ms=latency_ms,
            **extra,
        )

    @classmethod
    def budget_exhausted(
        cls,
        budget_type: str,
        current_usd: float,
        limit_usd: float,
        **extra: Any,
    ) -> None:
        """记录预算耗尽事件。"""
        cls._log.warning(
            "budget_exhausted",
            event_type="budget",
            budget_type=budget_type,
            current_usd=round(current_usd, 4),
            limit_usd=limit_usd,
            **extra,
        )

    @classmethod
    def source_fetch_failed(
        cls,
        source_id: str,
        error: str,
        error_streak: int | None = None,
        **extra: Any,
    ) -> None:
        """记录源抓取失败事件。"""
        cls._log.warning(
            "source_fetch_failed",
            event_type="ingest_error",
            source_id=source_id,
            error=error,
            error_streak=error_streak,
            **extra,
        )

    @classmethod
    def email_sent(
        cls,
        goal_id: str,
        to_email: str,
        email_type: str,
        success: bool,
        **extra: Any,
    ) -> None:
        """记录邮件发送事件。"""
        level = "info" if success else "warning"
        getattr(cls._log, level)(
            "email_sent",
            event_type="email",
            goal_id=goal_id,
            to_email=to_email,
            email_type=email_type,
            success=success,
            **extra,
        )

    @classmethod
    def notification_read(
        cls,
        notification_id: str,
        goal_id: str,
        user_id: str,
        **extra: Any,
    ) -> None:
        """记录通知已读事件。"""
        cls._log.info(
            "notification_read",
            event_type="notification",
            notification_id=notification_id,
            goal_id=goal_id,
            user_id=user_id,
            **extra,
        )

    @classmethod
    def feedback_submitted(
        cls,
        feedback_id: str,
        item_id: str,
        goal_id: str,
        user_id: str,
        feedback: str,
        block_source: bool,
        **extra: Any,
    ) -> None:
        """记录用户反馈事件。"""
        cls._log.info(
            "feedback_submitted",
            event_type="feedback",
            feedback_id=feedback_id,
            item_id=item_id,
            goal_id=goal_id,
            user_id=user_id,
            feedback=feedback,
            block_source=block_source,
            **extra,
        )

    @classmethod
    def click_tracked(
        cls,
        item_id: str,
        goal_id: str | None,
        channel: str,
        **extra: Any,
    ) -> None:
        """记录点击追踪事件。"""
        cls._log.info(
            "click_tracked",
            event_type="click",
            item_id=item_id,
            goal_id=goal_id,
            channel=channel,
            **extra,
        )

    @classmethod
    def feature_degraded(
        cls,
        feature: str,
        reason: str,
        **extra: Any,
    ) -> None:
        """记录功能降级事件。"""
        cls._log.warning(
            "feature_degraded",
            event_type="degradation",
            feature=feature,
            reason=reason,
            **extra,
        )
