"""Goal command handlers."""

import re
from uuid import uuid4

from loguru import logger

from src.modules.goals.application.commands import (
    ArchiveGoalCommand,
    CreateGoalCommand,
    DeleteGoalCommand,
    PauseGoalCommand,
    ResumeGoalCommand,
    UpdateGoalCommand,
)
from src.modules.goals.domain.entities import (
    Goal,
    GoalPriorityTerm,
    GoalPushConfig,
    TermType,
)
from src.modules.goals.domain.events import GoalCreatedEvent, GoalTermsUpdatedEvent
from src.modules.goals.domain.exceptions import (
    GoalAccessDeniedError,
    GoalNotFoundError,
    InvalidBatchWindowError,
    TooManyBatchWindowsError,
)
from src.modules.goals.domain.repository import (
    GoalPriorityTermRepository,
    GoalPushConfigRepository,
    GoalRepository,
)


def _validate_time_format(time_str: str) -> bool:
    """Validate HH:MM time format."""
    pattern = r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    return bool(re.match(pattern, time_str))


class CreateGoalHandler:
    """Handle goal creation."""

    def __init__(
        self,
        goal_repository: GoalRepository,
        push_config_repository: GoalPushConfigRepository,
        term_repository: GoalPriorityTermRepository,
    ):
        self.goal_repository = goal_repository
        self.push_config_repository = push_config_repository
        self.term_repository = term_repository
        self.logger = logger

    async def handle(self, command: CreateGoalCommand) -> Goal:
        """Create a new goal with config and terms."""
        # Validate batch windows
        if command.batch_windows:
            if len(command.batch_windows) > 3:
                raise TooManyBatchWindowsError()
            for window in command.batch_windows:
                if not _validate_time_format(window):
                    raise InvalidBatchWindowError(window)

        if command.digest_send_time and not _validate_time_format(
            command.digest_send_time
        ):
            raise InvalidBatchWindowError(command.digest_send_time)

        # Create goal
        goal = Goal(
            id=str(uuid4()),
            user_id=command.user_id,
            name=command.name,
            description=command.description,
            priority_mode=command.priority_mode,
        )
        goal.add_domain_event(
            GoalCreatedEvent(
                goal_id=goal.id,
                user_id=command.user_id,
                name=command.name,
            )
        )

        await self.goal_repository.create(goal)

        # Create push config
        push_config = GoalPushConfig(
            id=str(uuid4()),
            goal_id=goal.id,
            batch_windows=command.batch_windows or ["12:30", "18:30"],
            digest_send_time=command.digest_send_time or "09:00",
            batch_enabled=command.batch_enabled
            if command.batch_enabled is not None
            else True,
        )
        await self.push_config_repository.create(push_config)

        # Create terms
        terms_to_create: list[GoalPriorityTerm] = []

        if command.priority_terms:
            for term in command.priority_terms:
                if term.strip():
                    terms_to_create.append(
                        GoalPriorityTerm(
                            id=str(uuid4()),
                            goal_id=goal.id,
                            term=term.strip(),
                            term_type=TermType.MUST,
                        )
                    )

        if command.negative_terms:
            for term in command.negative_terms:
                if term.strip():
                    terms_to_create.append(
                        GoalPriorityTerm(
                            id=str(uuid4()),
                            goal_id=goal.id,
                            term=term.strip(),
                            term_type=TermType.NEGATIVE,
                        )
                    )

        if terms_to_create:
            await self.term_repository.bulk_create(terms_to_create)

        self.logger.info(f"Created goal: {goal.name} for user {command.user_id}")

        return goal


class UpdateGoalHandler:
    """Handle goal update."""

    def __init__(
        self,
        goal_repository: GoalRepository,
        push_config_repository: GoalPushConfigRepository,
        term_repository: GoalPriorityTermRepository,
    ):
        self.goal_repository = goal_repository
        self.push_config_repository = push_config_repository
        self.term_repository = term_repository
        self.logger = logger

    async def handle(self, command: UpdateGoalCommand) -> Goal:
        """Update a goal."""
        goal = await self.goal_repository.get_by_id(command.goal_id)
        if not goal:
            raise GoalNotFoundError(command.goal_id)

        if goal.user_id != command.user_id:
            raise GoalAccessDeniedError(command.goal_id)

        # Validate batch windows
        if command.batch_windows:
            if len(command.batch_windows) > 3:
                raise TooManyBatchWindowsError()
            for window in command.batch_windows:
                if not _validate_time_format(window):
                    raise InvalidBatchWindowError(window)

        if command.digest_send_time and not _validate_time_format(
            command.digest_send_time
        ):
            raise InvalidBatchWindowError(command.digest_send_time)

        # Update goal info
        goal.update_info(
            name=command.name,
            description=command.description,
            priority_mode=command.priority_mode,
        )
        await self.goal_repository.update(goal)

        # Update push config if provided
        if (
            command.batch_windows
            or command.digest_send_time
            or command.batch_enabled is not None
        ):
            push_config = await self.push_config_repository.get_by_goal_id(goal.id)
            if push_config:
                if command.batch_windows:
                    push_config.update_windows(command.batch_windows)
                if command.batch_enabled is not None:
                    push_config.batch_enabled = command.batch_enabled
                if command.digest_send_time:
                    push_config.update_digest_time(command.digest_send_time)
                await self.push_config_repository.update(push_config)

        # Update terms if provided
        if command.priority_terms is not None or command.negative_terms is not None:
            await self.term_repository.delete_all_for_goal(goal.id)

            terms_to_create: list[GoalPriorityTerm] = []

            if command.priority_terms:
                for term in command.priority_terms:
                    if term.strip():
                        terms_to_create.append(
                            GoalPriorityTerm(
                                id=str(uuid4()),
                                goal_id=goal.id,
                                term=term.strip(),
                                term_type=TermType.MUST,
                            )
                        )

            if command.negative_terms:
                for term in command.negative_terms:
                    if term.strip():
                        terms_to_create.append(
                            GoalPriorityTerm(
                                id=str(uuid4()),
                                goal_id=goal.id,
                                term=term.strip(),
                                term_type=TermType.NEGATIVE,
                            )
                        )

            if terms_to_create:
                await self.term_repository.bulk_create(terms_to_create)

            priority_count = len(
                [t for t in terms_to_create if t.term_type == TermType.MUST]
            )
            negative_count = len(
                [t for t in terms_to_create if t.term_type == TermType.NEGATIVE]
            )

            goal.add_domain_event(
                GoalTermsUpdatedEvent(
                    goal_id=goal.id,
                    priority_terms_count=priority_count,
                    negative_terms_count=negative_count,
                )
            )

        self.logger.info(f"Updated goal: {goal.name}")

        return goal


class PauseGoalHandler:
    """Handle goal pause."""

    def __init__(self, goal_repository: GoalRepository):
        self.goal_repository = goal_repository
        self.logger = logger

    async def handle(self, command: PauseGoalCommand) -> Goal:
        goal = await self.goal_repository.get_by_id(command.goal_id)
        if not goal:
            raise GoalNotFoundError(command.goal_id)

        if goal.user_id != command.user_id:
            raise GoalAccessDeniedError(command.goal_id)

        goal.pause()
        await self.goal_repository.update(goal)
        self.logger.info(f"Paused goal: {goal.name}")

        return goal


class ResumeGoalHandler:
    """Handle goal resume."""

    def __init__(self, goal_repository: GoalRepository):
        self.goal_repository = goal_repository
        self.logger = logger

    async def handle(self, command: ResumeGoalCommand) -> Goal:
        goal = await self.goal_repository.get_by_id(command.goal_id)
        if not goal:
            raise GoalNotFoundError(command.goal_id)

        if goal.user_id != command.user_id:
            raise GoalAccessDeniedError(command.goal_id)

        goal.resume()
        await self.goal_repository.update(goal)
        self.logger.info(f"Resumed goal: {goal.name}")

        return goal


class ArchiveGoalHandler:
    """Handle goal archive."""

    def __init__(self, goal_repository: GoalRepository):
        self.goal_repository = goal_repository
        self.logger = logger

    async def handle(self, command: ArchiveGoalCommand) -> Goal:
        goal = await self.goal_repository.get_by_id(command.goal_id)
        if not goal:
            raise GoalNotFoundError(command.goal_id)

        if goal.user_id != command.user_id:
            raise GoalAccessDeniedError(command.goal_id)

        goal.archive()
        await self.goal_repository.update(goal)
        self.logger.info(f"Archived goal: {goal.name}")

        return goal


class DeleteGoalHandler:
    """Handle goal deletion (soft delete)."""

    def __init__(self, goal_repository: GoalRepository):
        self.goal_repository = goal_repository
        self.logger = logger

    async def handle(self, command: DeleteGoalCommand) -> bool:
        goal = await self.goal_repository.get_by_id(command.goal_id)
        if not goal:
            raise GoalNotFoundError(command.goal_id)

        if goal.user_id != command.user_id:
            raise GoalAccessDeniedError(command.goal_id)

        result = await self.goal_repository.delete(goal)
        self.logger.info(f"Deleted goal: {goal.name}")

        return result
