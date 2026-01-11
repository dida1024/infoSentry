"""Celery 队列定义。

根据 TECH_SPEC_v0.md 第 7.1 节，按功能拆分 5 个独立队列：
- q_ingest: 抓取任务（NEWSNOW/RSS/SITE）
- q_embed: 向量化任务
- q_match: 匹配计算任务
- q_agent: Agent 决策任务
- q_email: 邮件发送任务
"""

from enum import StrEnum


class Queues(StrEnum):
    """Celery 队列枚举。"""

    INGEST = "q_ingest"
    EMBED = "q_embed"
    MATCH = "q_match"
    AGENT = "q_agent"
    EMAIL = "q_email"

    @classmethod
    def all_queues(cls) -> list[str]:
        """返回所有队列名称列表。"""
        return [q.value for q in cls]


# 队列路由配置
# 任务名称模式 -> 队列
TASK_ROUTES = {
    # 抓取相关任务
    "src.modules.*.tasks.ingest_*": {"queue": Queues.INGEST},
    "src.modules.sources.tasks.*": {"queue": Queues.INGEST},
    # 向量化任务
    "src.modules.*.tasks.embed_*": {"queue": Queues.EMBED},
    "src.modules.items.tasks.embed_*": {"queue": Queues.EMBED},
    # 匹配任务
    "src.modules.*.tasks.match_*": {"queue": Queues.MATCH},
    "src.modules.items.tasks.match_*": {"queue": Queues.MATCH},
    # Agent 决策任务
    "src.modules.agent.tasks.*": {"queue": Queues.AGENT},
    "src.modules.*.tasks.agent_*": {"queue": Queues.AGENT},
    # 邮件发送任务
    "src.modules.*.tasks.email_*": {"queue": Queues.EMAIL},
    "src.modules.push.tasks.send_*": {"queue": Queues.EMAIL},
}


# 队列优先级配置（数字越小优先级越高）
QUEUE_PRIORITIES = {
    Queues.AGENT: 1,  # Agent 决策优先
    Queues.EMAIL: 2,  # 邮件发送次之
    Queues.MATCH: 3,  # 匹配计算
    Queues.EMBED: 4,  # 向量化
    Queues.INGEST: 5,  # 抓取最后
}
