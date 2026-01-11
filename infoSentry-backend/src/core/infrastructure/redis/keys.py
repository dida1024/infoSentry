"""Redis Key 命名规范。

根据 ARCHITECTURE_DECISIONS.md 的决策，Redis 用于：
- Immediate Buffer: 5 分钟合并窗口
- Rate Limit: 速率限制计数器
- Feature Flags: 动态配置缓存
"""


class RedisKeys:
    """Redis Key 命名空间管理。"""

    # Immediate 合并缓冲区
    # buffer:immediate:{goal_id}:{time_bucket}
    IMMEDIATE_BUFFER_PREFIX = "buffer:immediate"

    # 速率限制
    # ratelimit:{resource}:{identifier}:{window}
    RATE_LIMIT_PREFIX = "ratelimit"

    # 动态配置
    # config:{key}
    CONFIG_PREFIX = "config"

    # 锁
    # lock:{resource}
    LOCK_PREFIX = "lock"

    # 健康检查
    HEALTH_CHECK_KEY = "health:ping"

    @classmethod
    def immediate_buffer(cls, goal_id: str, time_bucket: str) -> str:
        """生成 Immediate 合并缓冲区 key。

        Args:
            goal_id: 目标 ID
            time_bucket: 时间桶标识（如 2025-01-06T10:05）

        Returns:
            格式化的 Redis key
        """
        return f"{cls.IMMEDIATE_BUFFER_PREFIX}:{goal_id}:{time_bucket}"

    @classmethod
    def rate_limit(cls, resource: str, identifier: str, window: str) -> str:
        """生成速率限制 key。

        Args:
            resource: 资源类型（如 embed, judge, ingest）
            identifier: 标识符（如 daily, minute）
            window: 时间窗口（如 2025-01-06）

        Returns:
            格式化的 Redis key
        """
        return f"{cls.RATE_LIMIT_PREFIX}:{resource}:{identifier}:{window}"

    @classmethod
    def config(cls, key: str) -> str:
        """生成配置 key。

        Args:
            key: 配置项名称

        Returns:
            格式化的 Redis key
        """
        return f"{cls.CONFIG_PREFIX}:{key}"

    @classmethod
    def lock(cls, resource: str) -> str:
        """生成锁 key。

        Args:
            resource: 资源名称

        Returns:
            格式化的 Redis key
        """
        return f"{cls.LOCK_PREFIX}:{resource}"

    @classmethod
    def immediate_buffer_pattern(cls, goal_id: str | None = None) -> str:
        """生成 Immediate 缓冲区模式匹配 key。

        Args:
            goal_id: 可选的目标 ID，不提供则匹配所有

        Returns:
            用于 SCAN/KEYS 的模式
        """
        if goal_id:
            return f"{cls.IMMEDIATE_BUFFER_PREFIX}:{goal_id}:*"
        return f"{cls.IMMEDIATE_BUFFER_PREFIX}:*"
