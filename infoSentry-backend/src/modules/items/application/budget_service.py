"""预算熔断服务。

管理 embedding 和 judge（LLM 判别）的预算使用，支持：
- 日预算检查
- 熔断状态管理
- 使用量记录
"""

from datetime import UTC, datetime
from typing import Any

from loguru import logger

from src.core.config import settings
from src.core.domain.ports.kv import KVClient


class BudgetStatus:
    """预算状态。"""

    def __init__(
        self,
        date: str,
        embedding_tokens: int = 0,
        judge_tokens: int = 0,
        usd_est: float = 0.0,
        embedding_disabled: bool = False,
        judge_disabled: bool = False,
    ):
        self.date = date
        self.embedding_tokens = embedding_tokens
        self.judge_tokens = judge_tokens
        self.usd_est = usd_est
        self.embedding_disabled = embedding_disabled
        self.judge_disabled = judge_disabled

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "embedding_tokens": self.embedding_tokens,
            "judge_tokens": self.judge_tokens,
            "usd_est": self.usd_est,
            "embedding_disabled": self.embedding_disabled,
            "judge_disabled": self.judge_disabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BudgetStatus":
        return cls(
            date=data.get("date", ""),
            embedding_tokens=data.get("embedding_tokens", 0),
            judge_tokens=data.get("judge_tokens", 0),
            usd_est=data.get("usd_est", 0.0),
            embedding_disabled=data.get("embedding_disabled", False),
            judge_disabled=data.get("judge_disabled", False),
        )


class BudgetService:
    """预算熔断服务。

    使用 Redis 存储当日预算状态，支持：
    - 检查是否允许继续使用 embedding/judge
    - 记录使用量
    - 触发熔断
    """

    # Redis key 前缀
    BUDGET_KEY_PREFIX = "budget:daily"

    def __init__(self, redis_client: KVClient):
        self.redis = redis_client

    def _get_today_key(self) -> str:
        """获取今日的 Redis key。"""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        return f"{self.BUDGET_KEY_PREFIX}:{today}"

    async def get_status(self) -> BudgetStatus:
        """获取当日预算状态。"""
        key = self._get_today_key()
        data = await self.redis.get_json(key)

        if data:
            return BudgetStatus.from_dict(data)

        # 返回默认状态
        return BudgetStatus(
            date=datetime.now(UTC).strftime("%Y-%m-%d"),
        )

    async def _save_status(self, status: BudgetStatus) -> None:
        """保存预算状态。"""
        key = self._get_today_key()
        # 设置 24 小时过期
        await self.redis.set_json(key, status.to_dict(), ex=86400)

    async def check_embedding_budget(self) -> tuple[bool, str | None]:
        """检查是否允许继续使用 embedding。

        Returns:
            (是否允许, 原因)
        """
        # 检查全局开关
        if not settings.EMBEDDING_ENABLED:
            return False, "Embedding is disabled globally"

        status = await self.get_status()

        # 检查熔断标志
        if status.embedding_disabled:
            return False, "Embedding is disabled due to budget"

        # 检查日预算
        if status.usd_est >= settings.DAILY_USD_BUDGET:
            # 触发熔断
            status.embedding_disabled = True
            await self._save_status(status)
            logger.warning(f"Embedding budget exhausted: ${status.usd_est:.4f}")
            return False, f"Daily budget exhausted: ${status.usd_est:.4f}"

        # 检查 embedding 次数限制
        estimated_calls = status.embedding_tokens // 500  # 约 500 tokens/item
        if estimated_calls >= settings.EMBED_PER_DAY:
            status.embedding_disabled = True
            await self._save_status(status)
            logger.warning(f"Embedding count limit reached: {estimated_calls}")
            return False, f"Daily embedding limit reached: {estimated_calls}"

        return True, None

    async def check_judge_budget(self) -> tuple[bool, str | None]:
        """检查是否允许继续使用 LLM 判别。

        Returns:
            (是否允许, 原因)
        """
        # 检查全局开关
        if not settings.LLM_ENABLED:
            return False, "LLM is disabled globally"

        status = await self.get_status()

        # 检查熔断标志
        if status.judge_disabled:
            return False, "Judge is disabled due to budget"

        # 检查日预算
        if status.usd_est >= settings.DAILY_USD_BUDGET:
            status.judge_disabled = True
            await self._save_status(status)
            logger.warning(f"Judge budget exhausted: ${status.usd_est:.4f}")
            return False, f"Daily budget exhausted: ${status.usd_est:.4f}"

        # 检查 judge 次数限制
        estimated_calls = status.judge_tokens // 200  # 约 200 tokens/call
        if estimated_calls >= settings.JUDGE_PER_DAY:
            status.judge_disabled = True
            await self._save_status(status)
            logger.warning(f"Judge count limit reached: {estimated_calls}")
            return False, f"Daily judge limit reached: {estimated_calls}"

        return True, None

    async def record_embedding_usage(self, tokens: int) -> None:
        """记录 embedding token 使用量。"""
        status = await self.get_status()
        status.embedding_tokens += tokens

        # 更新费用估算
        cost = (tokens / 1000) * settings.EMBED_PRICE_PER_1K
        status.usd_est += cost

        await self._save_status(status)

        logger.debug(
            f"Recorded embedding usage: {tokens} tokens, "
            f"total: {status.embedding_tokens}, "
            f"cost: ${status.usd_est:.4f}"
        )

    async def record_judge_usage(self, tokens: int) -> None:
        """记录 judge token 使用量。"""
        status = await self.get_status()
        status.judge_tokens += tokens

        # 更新费用估算
        cost = (tokens / 1000) * settings.JUDGE_PRICE_PER_1K
        status.usd_est += cost

        await self._save_status(status)

        logger.debug(
            f"Recorded judge usage: {tokens} tokens, "
            f"total: {status.judge_tokens}, "
            f"cost: ${status.usd_est:.4f}"
        )

    async def reset_daily_budget(self) -> None:
        """重置每日预算（用于测试或手动重置）。"""
        key = self._get_today_key()
        await self.redis.delete(key)
        logger.info("Daily budget reset")

    async def force_disable_embedding(self) -> None:
        """强制禁用 embedding。"""
        status = await self.get_status()
        status.embedding_disabled = True
        await self._save_status(status)
        logger.warning("Embedding force disabled")

    async def force_disable_judge(self) -> None:
        """强制禁用 judge。"""
        status = await self.get_status()
        status.judge_disabled = True
        await self._save_status(status)
        logger.warning("Judge force disabled")

    async def enable_embedding(self) -> None:
        """启用 embedding（解除熔断）。"""
        status = await self.get_status()
        status.embedding_disabled = False
        await self._save_status(status)
        logger.info("Embedding enabled")

    async def enable_judge(self) -> None:
        """启用 judge（解除熔断）。"""
        status = await self.get_status()
        status.judge_disabled = False
        await self._save_status(status)
        logger.info("Judge enabled")
