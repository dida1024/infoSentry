"""User AI budget usage service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import structlog

from src.core.config import settings
from src.core.domain.exceptions import ValidationError
from src.modules.items.application.budget_service import BudgetService
from src.modules.users.domain.entities import UserBudgetDaily
from src.modules.users.domain.repository import UserBudgetDailyRepository

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class UserBudgetUsageDaySummary:
    date: str
    embedding_tokens_est: int
    judge_tokens_est: int
    usd_est: float
    daily_limit: float
    usage_percent: float


@dataclass(frozen=True)
class UserBudgetUsageSummary:
    user_id: str
    start_date: str
    end_date: str
    total_embedding_tokens_est: int
    total_judge_tokens_est: int
    total_usd_est: float
    daily_limit: float
    days: list[UserBudgetUsageDaySummary]


class UserBudgetUsageService:
    """Track and query per-user daily AI budget usage."""

    def __init__(self, budget_repository: UserBudgetDailyRepository):
        self.budget_repository = budget_repository

    async def record_judge_usage(self, user_id: str, tokens: int) -> None:
        """Record judge token usage for a user."""
        if tokens <= 0:
            return

        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        budget = await self.budget_repository.get_or_create(user_id, date_str)
        budget.add_judge_tokens(tokens)

        cost = (tokens / 1000) * BudgetService.JUDGE_PRICE_PER_1K
        budget.add_cost(cost)

        await self.budget_repository.update(budget)
        logger.info(
            "user_budget_judge_usage_recorded",
            user_id=user_id,
            date=date_str,
            tokens=tokens,
            usd_est=round(budget.usd_est, 6),
        )

    async def record_embedding_usage(self, user_id: str, tokens: int) -> None:
        """Record embedding token usage for a user."""
        if tokens <= 0:
            return

        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        budget = await self.budget_repository.get_or_create(user_id, date_str)
        budget.add_embedding_tokens(tokens)

        cost = (tokens / 1000) * BudgetService.EMBED_PRICE_PER_1K
        budget.add_cost(cost)

        await self.budget_repository.update(budget)
        logger.info(
            "user_budget_embedding_usage_recorded",
            user_id=user_id,
            date=date_str,
            tokens=tokens,
            usd_est=round(budget.usd_est, 6),
        )

    async def get_daily_usage(
        self, user_id: str, start_date: date, end_date: date
    ) -> list[UserBudgetDaily]:
        """Get per-day usage, filling missing dates with zeros."""
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
        existing = await self.budget_repository.list_by_user_date_range(
            user_id, start_str, end_str
        )
        by_date = {budget.date: budget for budget in existing}

        filled: list[UserBudgetDaily] = []
        current = start_date
        while current <= end_date:
            current_str = current.isoformat()
            budget = by_date.get(
                current_str,
                UserBudgetDaily(
                    user_id=user_id,
                    date=current_str,
                ),
            )
            filled.append(budget)
            current += timedelta(days=1)

        logger.info(
            "user_budget_usage_retrieved",
            user_id=user_id,
            start_date=start_str,
            end_date=end_str,
            days=len(filled),
        )
        return filled

    async def get_usage_summary(
        self, user_id: str, start_date: date, end_date: date
    ) -> UserBudgetUsageSummary:
        """Get usage summary for a date range."""
        if end_date < start_date:
            raise ValidationError(
                "end_date must be greater than or equal to start_date"
            )
        daily_usage = await self.get_daily_usage(
            user_id=user_id, start_date=start_date, end_date=end_date
        )

        daily_limit = self.daily_limit()
        days: list[UserBudgetUsageDaySummary] = []
        total_embedding_tokens = 0
        total_judge_tokens = 0
        total_usd = 0.0

        for usage in daily_usage:
            total_embedding_tokens += usage.embedding_tokens_est
            total_judge_tokens += usage.judge_tokens_est
            total_usd += usage.usd_est
            usage_percent = (
                round((usage.usd_est / daily_limit) * 100, 2)
                if daily_limit > 0
                else 0.0
            )
            days.append(
                UserBudgetUsageDaySummary(
                    date=usage.date,
                    embedding_tokens_est=usage.embedding_tokens_est,
                    judge_tokens_est=usage.judge_tokens_est,
                    usd_est=round(usage.usd_est, 6),
                    daily_limit=daily_limit,
                    usage_percent=usage_percent,
                )
            )

        return UserBudgetUsageSummary(
            user_id=user_id,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            total_embedding_tokens_est=total_embedding_tokens,
            total_judge_tokens_est=total_judge_tokens,
            total_usd_est=round(total_usd, 6),
            daily_limit=daily_limit,
            days=days,
        )

    @staticmethod
    def daily_limit() -> float:
        """Current per-user daily USD limit."""
        return settings.DAILY_USD_BUDGET
