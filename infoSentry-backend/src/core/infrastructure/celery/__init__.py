"""Celery 配置与任务定义。"""

from src.core.infrastructure.celery.app import celery_app
from src.core.infrastructure.celery.queues import Queues

__all__ = ["celery_app", "Queues"]
