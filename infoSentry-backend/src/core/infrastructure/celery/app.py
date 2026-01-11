"""Celery 应用配置。

根据 TECH_SPEC_v0.md 和 RUNBOOK_VM.md 的要求：
- 使用 JSON 序列化
- 按功能拆分队列
- 支持任务重试与退避
- 配置定时任务（Beat）
"""

from celery import Celery
from kombu import Exchange, Queue

from src.core.config import settings
from src.core.infrastructure.celery.queues import TASK_ROUTES, Queues

# 创建 Celery 应用
celery_app = Celery("infosentry")

# 基础配置
celery_app.conf.update(
    # Broker & Backend
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    # 序列化配置
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,
    # 时区配置
    timezone=settings.TIMEZONE,
    enable_utc=True,
    # 任务配置
    task_track_started=True,
    task_time_limit=300,  # 5 分钟硬超时
    task_soft_time_limit=240,  # 4 分钟软超时
    # 重试配置
    task_default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY,
    task_max_retries=settings.CELERY_TASK_MAX_RETRIES,
    task_acks_late=True,  # 任务完成后才确认
    task_reject_on_worker_lost=True,  # Worker 丢失时拒绝任务
    # 结果配置
    result_expires=3600,  # 结果保留 1 小时
    # Worker 配置
    worker_prefetch_multiplier=1,  # 一次只取一个任务
    worker_concurrency=1,  # 默认并发数，实际由启动参数控制
)

# 队列配置
default_exchange = Exchange("default", type="direct")
celery_app.conf.task_queues = (
    Queue(Queues.INGEST, default_exchange, routing_key=Queues.INGEST),
    Queue(Queues.EMBED, default_exchange, routing_key=Queues.EMBED),
    Queue(Queues.MATCH, default_exchange, routing_key=Queues.MATCH),
    Queue(Queues.AGENT, default_exchange, routing_key=Queues.AGENT),
    Queue(Queues.EMAIL, default_exchange, routing_key=Queues.EMAIL),
)

# 任务路由
celery_app.conf.task_routes = TASK_ROUTES

# 默认队列
celery_app.conf.task_default_queue = Queues.INGEST

# 定时任务配置（Celery Beat）
# 这里只定义调度配置，具体任务在各模块中注册
celery_app.conf.beat_schedule = {
    # 抓取调度：每分钟检查待抓取的源
    "check-sources-to-fetch": {
        "task": "src.modules.sources.tasks.check_and_dispatch_fetches",
        "schedule": 60.0,  # 每分钟
        "options": {"queue": Queues.INGEST},
    },
    # Digest 调度：每日检查是否需要发送 Digest
    "check-digest-send": {
        "task": "src.modules.agent.tasks.check_and_send_digest",
        "schedule": 300.0,  # 每 5 分钟检查
        "options": {"queue": Queues.AGENT},
    },
    # Batch 窗口调度：每分钟检查是否有窗口触发
    "check-batch-windows": {
        "task": "src.modules.agent.tasks.check_and_trigger_batch_windows",
        "schedule": 60.0,  # 每分钟
        "options": {"queue": Queues.AGENT},
    },
    # Immediate 合并检查：每分钟检查合并缓冲区
    "check-immediate-coalesce": {
        "task": "src.modules.push.tasks.check_and_coalesce_immediate",
        "schedule": 60.0,  # 每分钟
        "options": {"queue": Queues.EMAIL},
    },
    # 预算检查：每小时检查并更新预算状态
    "check-daily-budget": {
        "task": "src.modules.agent.tasks.check_and_update_budget",
        "schedule": 3600.0,  # 每小时
        "options": {"queue": Queues.AGENT},
    },
    # 嵌入调度：每分钟处理待嵌入的 Items
    "process-pending-embeddings": {
        "task": "src.modules.items.tasks.embed_pending_items",
        "schedule": 60.0,  # 每分钟
        "options": {"queue": Queues.EMBED},
        "args": (50,),  # 每次处理 50 条
    },
    # 健康检查：每 5 分钟执行一次
    "run-health-check": {
        "task": "src.modules.agent.tasks.run_health_check",
        "schedule": 300.0,  # 每 5 分钟
        "options": {"queue": Queues.AGENT},
    },
}

# 自动发现任务
# 任务应在各模块的 tasks.py 中定义
celery_app.autodiscover_tasks(
    [
        "src.modules.sources",
        "src.modules.items",
        "src.modules.push",
        "src.modules.agent",
    ],
    related_name="tasks",
)
