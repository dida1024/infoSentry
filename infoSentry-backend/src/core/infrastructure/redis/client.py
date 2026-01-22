"""Redis 客户端封装。

提供统一的 Redis 访问接口，支持：
- 连接池管理
- 健康检查
- 常用操作封装
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import redis.asyncio as aioredis
from loguru import logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

from src.core.config import settings
from src.core.infrastructure.health import HealthStatus, RedisHealthResult
from src.core.infrastructure.redis.keys import RedisKeys


class RedisUnavailableError(RuntimeError):
    """Redis 不可用（连接失败/超时等）。"""


class RedisClient:
    """Redis 客户端封装类。"""

    def __init__(self, url: str | None = None):
        """初始化 Redis 客户端。

        Args:
            url: Redis 连接 URL，默认使用配置中的 REDIS_URL
        """
        self._url = url or settings.REDIS_URL
        self._client: Redis | None = None

    @property
    def client(self) -> Redis:
        """获取 Redis 客户端实例（延迟初始化）。"""
        if self._client is None:
            self._client = aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=10.0,  # 读写超时 10 秒
                socket_connect_timeout=5.0,  # 连接超时 5 秒
                retry_on_timeout=True,  # 超时后重试
            )
        return self._client

    async def close(self) -> None:
        """关闭 Redis 连接。"""
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def ping(self) -> bool:
        """检查 Redis 连接是否正常。

        Returns:
            连接正常返回 True，否则返回 False
        """
        try:
            return await self.client.ping()
        except Exception as e:
            logger.warning(f"Redis ping failed: {e}")
            return False

    @asynccontextmanager
    async def ensure_available(
        self,
        *,
        timeout: float = 5.0,
        close_on_exit: bool = False,
    ) -> AsyncGenerator[RedisClient, None]:
        """确保进入上下文时 Redis 连接可用。

        适用于需要在执行一段逻辑前先做连通性检查的场景（如 Celery 定时任务）。

        Usage:
            redis_client = RedisClient()
            try:
                async with redis_client.ensure_available(timeout=5.0, close_on_exit=True):
                    # Redis 操作...
                    ...
            except RedisUnavailableError:
                # Redis 不可用，按需降级/跳过
                ...
        """
        try:
            # 这里直接调用底层 client.ping()，避免与 self.ping() 的日志重复。
            ok = await asyncio.wait_for(self.client.ping(), timeout=timeout)
            if not ok:
                raise RedisUnavailableError("Redis ping returned falsy result")
        except TimeoutError as e:
            if close_on_exit:
                await self.close()
            raise RedisUnavailableError("Redis ping timeout") from e
        except RedisUnavailableError:
            if close_on_exit:
                await self.close()
            raise
        except Exception as e:
            if close_on_exit:
                await self.close()
            raise RedisUnavailableError(f"Redis ping failed: {e}") from e

        try:
            yield self
        finally:
            if close_on_exit:
                await self.close()

    async def health_check(self) -> RedisHealthResult:
        """执行 Redis 健康检查。

        检查 Redis 连接状态和版本信息。

        Returns:
            RedisHealthResult: 健康检查结果
        """
        try:
            is_connected = await self.ping()
            info = await self.client.info("server") if is_connected else {}
            return RedisHealthResult(
                status=HealthStatus.OK if is_connected else HealthStatus.ERROR,
                connected=is_connected,
                version=info.get("redis_version", "unknown"),
            )
        except Exception as e:
            return RedisHealthResult(
                status=HealthStatus.ERROR,
                connected=False,
                error=str(e),
            )

    # ============ 缓存操作 ============

    async def get(self, key: str) -> str | None:
        """获取字符串值。"""
        return await self.client.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ex: int | timedelta | None = None,
        nx: bool = False,
    ) -> bool:
        """设置字符串值。

        Args:
            key: 键名
            value: 值
            ex: 过期时间（秒或 timedelta）
            nx: 仅当键不存在时设置

        Returns:
            设置成功返回 True
        """
        return await self.client.set(key, value, ex=ex, nx=nx)

    async def delete(self, *keys: str) -> int:
        """删除一个或多个键。"""
        return await self.client.delete(*keys)

    async def exists(self, *keys: str) -> int:
        """检查键是否存在。"""
        return await self.client.exists(*keys)

    async def expire(self, key: str, seconds: int) -> bool:
        """设置键的过期时间。"""
        return await self.client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        """获取键的剩余生存时间（秒）。"""
        return await self.client.ttl(key)

    # ============ JSON 操作 ============

    async def get_json(self, key: str) -> Any | None:
        """获取 JSON 值。"""
        value = await self.get(key)
        if value is None:
            return None
        return json.loads(value)

    async def set_json(
        self,
        key: str,
        value: Any,
        ex: int | timedelta | None = None,
    ) -> bool:
        """设置 JSON 值。"""
        return await self.set(key, json.dumps(value, ensure_ascii=False), ex=ex)

    # ============ 计数器操作 ============

    async def incr(self, key: str, amount: int = 1) -> int:
        """增加计数器。"""
        return await self.client.incrby(key, amount)

    async def decr(self, key: str, amount: int = 1) -> int:
        """减少计数器。"""
        return await self.client.decrby(key, amount)

    # ============ 列表操作 ============

    async def lpush(self, key: str, *values: str) -> int:
        """向列表头部插入元素。"""
        return await self.client.lpush(key, *values)

    async def rpush(self, key: str, *values: str) -> int:
        """向列表尾部插入元素。"""
        return await self.client.rpush(key, *values)

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        """获取列表指定范围的元素。"""
        return await self.client.lrange(key, start, end)

    async def llen(self, key: str) -> int:
        """获取列表长度。"""
        return await self.client.llen(key)

    # ============ 集合操作 ============

    async def sadd(self, key: str, *members: str) -> int:
        """向集合添加成员。"""
        return await self.client.sadd(key, *members)

    async def smembers(self, key: str) -> set[str]:
        """获取集合所有成员。"""
        return await self.client.smembers(key)

    async def sismember(self, key: str, member: str) -> bool:
        """检查成员是否在集合中。"""
        return await self.client.sismember(key, member)

    # ============ 速率限制 ============

    async def rate_limit_check(
        self,
        resource: str,
        identifier: str,
        window: str,
        limit: int,
        ttl: int = 60,
    ) -> tuple[bool, int]:
        """检查并更新速率限制。

        Args:
            resource: 资源类型
            identifier: 标识符
            window: 时间窗口
            limit: 限制数量
            ttl: key 过期时间（秒）

        Returns:
            (是否允许, 当前计数)
        """
        key = RedisKeys.rate_limit(resource, identifier, window)
        current = await self.incr(key)

        # 首次创建时设置过期时间
        if current == 1:
            await self.expire(key, ttl)

        return current <= limit, current

    async def get_rate_limit_count(
        self,
        resource: str,
        identifier: str,
        window: str,
    ) -> int:
        """获取当前速率限制计数。"""
        key = RedisKeys.rate_limit(resource, identifier, window)
        value = await self.get(key)
        return int(value) if value else 0

    # ============ 配置管理 ============

    async def get_config(self, key: str, default: Any = None) -> Any:
        """获取动态配置。"""
        value = await self.get_json(RedisKeys.config(key))
        return value if value is not None else default

    async def set_config(self, key: str, value: Any) -> bool:
        """设置动态配置。"""
        return await self.set_json(RedisKeys.config(key), value)

    # ============ 锁操作 ============

    async def acquire_lock(
        self,
        resource: str,
        ttl: int = 60,
    ) -> bool:
        """尝试获取分布式锁。

        Args:
            resource: 资源名称
            ttl: 锁过期时间（秒）

        Returns:
            获取成功返回 True
        """
        key = RedisKeys.lock(resource)
        return await self.set(key, "1", ex=ttl, nx=True)

    async def release_lock(self, resource: str) -> bool:
        """释放分布式锁。"""
        key = RedisKeys.lock(resource)
        return await self.delete(key) > 0

    # ============ Ingest 任务锁 ============

    async def acquire_ingest_lock(
        self,
        source_id: str,
        ttl: int = 600,
    ) -> bool:
        """尝试获取 Source 抓取任务锁。

        用于防止同一 Source 被并发抓取。

        Args:
            source_id: 信息源 ID
            ttl: 锁过期时间（秒），默认 10 分钟

        Returns:
            获取成功返回 True
        """
        key = RedisKeys.ingest_lock(source_id)
        return await self.set(key, "1", ex=ttl, nx=True)

    async def release_ingest_lock(self, source_id: str) -> bool:
        """释放 Source 抓取任务锁。

        Args:
            source_id: 信息源 ID

        Returns:
            释放成功返回 True
        """
        key = RedisKeys.ingest_lock(source_id)
        return await self.delete(key) > 0


@asynccontextmanager
async def get_async_redis_client(
    *,
    timeout: float = 5.0,
    url: str | None = None,
) -> AsyncGenerator[RedisClient, None]:
    """获取可用的 RedisClient（上下文管理器）。

    - 进入上下文时会执行 ping 校验，并带超时控制
    - 退出上下文时自动关闭连接（避免 Celery 的 asyncio.run() 跨事件循环复用问题）

    Usage:
        try:
            async with get_async_redis_client(timeout=5.0) as redis_client:
                await redis_client.set("k", "v")
        except RedisUnavailableError:
            ...
    """
    client = RedisClient(url=url)
    async with client.ensure_available(timeout=timeout, close_on_exit=True):
        yield client


# 全局 Redis 客户端实例
redis_client = RedisClient()


def get_redis_client() -> RedisClient:
    """获取 Redis 客户端依赖。"""
    return redis_client
