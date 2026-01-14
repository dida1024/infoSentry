"""Celery 队列定义。

根据 TECH_SPEC_v0.md 第 7.1 节，按功能拆分 5 个独立队列：
- q_ingest: 抓取任务（NEWSNOW/RSS/SITE）
- q_embed: 向量化任务
- q_match: 匹配计算任务
- q_agent: Agent 决策任务
- q_email: 邮件发送任务
"""

from src.core.domain.queues import Queues

# 队列路由配置
# 任务名称模式 -> 队列（使用字符串值）
TASK_ROUTES = {
    # 抓取相关任务
    "src.modules.*.tasks.ingest_*": {"queue": Queues.INGEST.value},
    "src.modules.sources.tasks.*": {"queue": Queues.INGEST.value},
    # 向量化任务
    "src.modules.*.tasks.embed_*": {"queue": Queues.EMBED.value},
    "src.modules.items.tasks.embed_*": {"queue": Queues.EMBED.value},
    # 匹配任务
    "src.modules.*.tasks.match_*": {"queue": Queues.MATCH.value},
    "src.modules.items.tasks.match_*": {"queue": Queues.MATCH.value},
    # Agent 决策任务
    "src.modules.agent.tasks.*": {"queue": Queues.AGENT.value},
    "src.modules.*.tasks.agent_*": {"queue": Queues.AGENT.value},
    # 邮件发送任务
    "src.modules.*.tasks.email_*": {"queue": Queues.EMAIL.value},
    "src.modules.push.tasks.send_*": {"queue": Queues.EMAIL.value},
}


# 队列优先级配置（数字越小优先级越高）
QUEUE_PRIORITIES = {
    Queues.AGENT: 1,  # Agent 决策优先
    Queues.EMAIL: 2,  # 邮件发送次之
    Queues.MATCH: 3,  # 匹配计算
    Queues.EMBED: 4,  # 向量化
    Queues.INGEST: 5,  # 抓取最后
}
