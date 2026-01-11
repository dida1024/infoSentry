"""Agent repository interfaces."""

from abc import abstractmethod
from datetime import datetime

from src.core.domain.repository import BaseRepository
from src.modules.agent.domain.entities import (
    AgentActionLedger,
    AgentRun,
    AgentRunStatus,
    AgentToolCall,
    AgentTrigger,
    BudgetDaily,
)


class AgentRunRepository(BaseRepository[AgentRun]):
    """Agent run repository interface."""

    @abstractmethod
    async def list_by_goal(
        self,
        goal_id: str,
        status: AgentRunStatus | None = None,
        trigger: AgentTrigger | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AgentRun], int]:
        """List runs by goal."""
        pass

    @abstractmethod
    async def list_recent(
        self,
        since: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AgentRun], int]:
        """List recent runs."""
        pass


class AgentToolCallRepository(BaseRepository[AgentToolCall]):
    """Agent tool call repository interface."""

    @abstractmethod
    async def list_by_run(self, run_id: str) -> list[AgentToolCall]:
        """List tool calls for a run."""
        pass


class AgentActionLedgerRepository(BaseRepository[AgentActionLedger]):
    """Agent action ledger repository interface."""

    @abstractmethod
    async def list_by_run(self, run_id: str) -> list[AgentActionLedger]:
        """List actions for a run."""
        pass


class BudgetDailyRepository(BaseRepository[BudgetDaily]):
    """Budget daily repository interface."""

    @abstractmethod
    async def get_by_date(self, date: str) -> BudgetDaily | None:
        """Get budget for a specific date."""
        pass

    @abstractmethod
    async def get_or_create_today(self) -> BudgetDaily:
        """Get or create today's budget record."""
        pass
