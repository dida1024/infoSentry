"""Runtime factory wiring agent orchestrator and dependencies."""

from typing import Any, Optional

from src.core.domain.events import EventBus
from src.core.infrastructure.ai.prompting.dependencies import (
    get_prompt_store as get_prompt_store_infra,
)
from src.modules.agent.application.logging_port import LoggingPort
from src.modules.agent.application.llm_service import LLMJudgeService
from src.modules.agent.application.orchestrator import AgentOrchestrator
from src.modules.agent.application.tools import create_default_registry
from src.modules.agent.infrastructure.logging import StructlogLoggingPort
from src.modules.agent.infrastructure.mappers import (
    AgentActionLedgerMapper,
    AgentRunMapper,
    AgentToolCallMapper,
)
from src.modules.agent.infrastructure.repositories import (
    PostgreSQLAgentActionLedgerRepository,
    PostgreSQLAgentRunRepository,
    PostgreSQLAgentToolCallRepository,
)
from src.modules.goals.infrastructure.mappers import GoalMapper
from src.modules.goals.infrastructure.repositories import PostgreSQLGoalRepository
from src.modules.items.application.budget_service import BudgetService
from src.modules.items.infrastructure.mappers import GoalItemMatchMapper, ItemMapper
from src.modules.items.infrastructure.repositories import (
    PostgreSQLGoalItemMatchRepository,
    PostgreSQLItemRepository,
)
from src.modules.push.infrastructure.mappers import PushDecisionMapper
from src.modules.push.infrastructure.repositories import (
    PostgreSQLPushDecisionRepository,
)
from src.modules.users.application.budget_service import UserBudgetUsageService
from src.modules.users.infrastructure.mappers import UserBudgetDailyMapper
from src.modules.users.infrastructure.repositories import (
    PostgreSQLUserBudgetDailyRepository,
)


class AgentRuntimeComponents:
    """Bundle of objects needed to run agent pipelines."""

    def __init__(
        self,
        orchestrator: AgentOrchestrator,
        match_repo: PostgreSQLGoalItemMatchRepository,
        decision_repo: PostgreSQLPushDecisionRepository,
        goal_repo: PostgreSQLGoalRepository,
        item_repo: PostgreSQLItemRepository,
        llm_service: LLMJudgeService,
    ) -> None:
        self.orchestrator = orchestrator
        self.match_repo = match_repo
        self.decision_repo = decision_repo
        self.goal_repo = goal_repo
        self.item_repo = item_repo
        self.llm_service = llm_service


class AgentRuntimeFactory:
    """Factory to build orchestrator and dependencies."""

    def __init__(
        self,
        *,
        session: Any,
        redis_client: Any,
        event_bus: EventBus,
        logging_port: Optional[LoggingPort] = None,
    ) -> None:
        self.session = session
        self.redis_client = redis_client
        self.event_bus = event_bus
        self.logging_port = logging_port or StructlogLoggingPort()

    def create(self) -> AgentRuntimeComponents:
        """Create orchestrator with repositories, tools, LLM services."""
        run_repo = PostgreSQLAgentRunRepository(
            self.session, AgentRunMapper(), self.event_bus
        )
        tool_call_repo = PostgreSQLAgentToolCallRepository(
            self.session, AgentToolCallMapper(), self.event_bus
        )
        ledger_repo = PostgreSQLAgentActionLedgerRepository(
            self.session, AgentActionLedgerMapper(), self.event_bus
        )
        match_repo = PostgreSQLGoalItemMatchRepository(
            self.session, GoalItemMatchMapper(), self.event_bus
        )
        decision_repo = PostgreSQLPushDecisionRepository(
            self.session, PushDecisionMapper(), self.event_bus
        )
        goal_repo = PostgreSQLGoalRepository(
            self.session, GoalMapper(), self.event_bus
        )
        item_repo = PostgreSQLItemRepository(
            self.session, ItemMapper(), self.event_bus
        )
        user_budget_repo = PostgreSQLUserBudgetDailyRepository(
            self.session, UserBudgetDailyMapper(), self.event_bus
        )

        budget_service = BudgetService(self.redis_client)
        user_budget_service = UserBudgetUsageService(user_budget_repo)
        prompt_store = get_prompt_store_infra()

        llm_service = LLMJudgeService(
            budget_service=budget_service,
            user_budget_service=user_budget_service,
            prompt_store=prompt_store,
        )

        tools = create_default_registry(
            goal_repository=goal_repo,
            term_repository=None,
            item_repository=item_repo,
            decision_repository=decision_repo,
            budget_service=budget_service,
            redis_client=self.redis_client,
            ledger_repo=ledger_repo,
        )

        orchestrator = AgentOrchestrator(
            run_repository=run_repo,
            tool_call_repository=tool_call_repo,
            ledger_repository=ledger_repo,
            tools=tools,
            llm_service=llm_service,
            logging_port=self.logging_port,
        )

        return AgentRuntimeComponents(
            orchestrator=orchestrator,
            match_repo=match_repo,
            decision_repo=decision_repo,
            goal_repo=goal_repo,
            item_repo=item_repo,
            llm_service=llm_service,
        )
