"""Goal application services."""

from loguru import logger

from src.core.config import settings
from src.modules.goals.application.models import (
    GoalData,
    GoalListData,
    GoalMatchData,
    GoalMatchListData,
    ItemData,
)
from src.modules.goals.domain.entities import (
    Goal,
    GoalPriorityTerm,
    GoalPushConfig,
    GoalStatus,
    TermType,
)
from src.modules.goals.domain.exceptions import GoalNotFoundError
from src.modules.goals.domain.repository import (
    GoalPriorityTermRepository,
    GoalPushConfigRepository,
    GoalRepository,
)
from src.modules.items.domain.entities import RankMode
from src.modules.items.domain.repository import GoalItemMatchRepository, ItemRepository
from src.modules.sources.domain.repository import SourceRepository


class GoalMatchQueryService:
    """Query service for goal matches."""

    def __init__(
        self,
        goal_repository: GoalRepository,
        match_repository: GoalItemMatchRepository,
        item_repository: ItemRepository,
        source_repository: SourceRepository,
    ) -> None:
        self.goal_repo = goal_repository
        self.match_repo = match_repository
        self.item_repo = item_repository
        self.source_repo = source_repository
        self.logger = logger.bind(service="GoalMatchQueryService")

    async def list_matches(
        self,
        goal_id: str,
        user_id: str,
        min_score: float | None = None,
        rank_mode: RankMode = RankMode.HYBRID,
        half_life_days: float | None = None,
        page: int = settings.DEFAULT_PAGE,
        page_size: int = settings.DEFAULT_PAGE_SIZE,
    ) -> GoalMatchListData:
        """List matches for a goal.

        Args:
            goal_id: Goal ID
            user_id: User ID for access check
            min_score: Minimum match score filter
            page: Page number
            page_size: Page size

        Returns:
            GoalMatchListData with paginated matches

        Raises:
            GoalNotFoundError: If goal not found or user has no access
        """
        effective_half_life = (
            half_life_days
            if half_life_days is not None and half_life_days > 0
            else settings.GOAL_MATCH_RANK_HALF_LIFE_DAYS
        )

        self.logger.info(
            f"Listing matches for goal {goal_id} for user {user_id} with min_score {min_score} "
            f"rank_mode {rank_mode.value} half_life_days {effective_half_life} "
            f"and page {page} and page_size {page_size}"
        )
        # Access check
        goal = await self.goal_repo.get_by_id(goal_id)
        if not goal or goal.user_id != user_id:
            raise GoalNotFoundError(goal_id)

        if min_score is not None and min_score <= 0:
            min_score = None

        deduped_matches, total = await self.match_repo.list_by_goal_deduped(
            goal_id=goal_id,
            min_score=min_score,
            rank_mode=rank_mode,
            half_life_days=effective_half_life,
            page=page,
            page_size=page_size,
        )

        if not deduped_matches:
            self.logger.info(
                f"No matches found for goal {goal_id} for user {user_id} with min_score {min_score} and page {page} and page_size {page_size}"
            )
            return GoalMatchListData(
                items=[],
                total=total,
                page=page,
                page_size=page_size,
            )

        # Batch fetch items and sources (avoid N+1 queries)
        item_ids = [match.item_id for match in deduped_matches]
        items_by_id = await self.item_repo.get_by_ids(item_ids)

        # Collect source IDs from fetched items
        source_ids = list({item.source_id for item in items_by_id.values()})
        sources_by_id = await self.source_repo.get_by_ids(source_ids)

        # Build items map
        items_map: dict[str, ItemData] = {}
        for match in deduped_matches:
            item = items_by_id.get(match.item_id)
            if item:
                source = sources_by_id.get(item.source_id)
                items_map[match.item_id] = ItemData(
                    id=item.id,
                    url=item.url,
                    title=item.title,
                    snippet=item.snippet,
                    summary=item.summary,
                    published_at=item.published_at,
                    ingested_at=item.ingested_at,
                    source_name=source.name if source else None,
                )

        # Build response
        match_items = [
            GoalMatchData(
                id=match.id,
                goal_id=match.goal_id,
                item_id=match.item_id,
                match_score=match.match_score,
                features_json=match.features_json,
                reasons_json=match.reasons_json,
                computed_at=match.computed_at,
                item=items_map.get(match.item_id),
            )
            for match in deduped_matches
        ]
        self.logger.info(
            f"Found {len(match_items)} matches for goal {goal_id} for user {user_id} with min_score {min_score} and page {page} and page_size {page_size}"
        )
        return GoalMatchListData(
            items=match_items,
            total=total,
            page=page,
            page_size=page_size,
        )


class GoalQueryService:
    """Goal query service for list/detail views."""

    def __init__(
        self,
        goal_repository: GoalRepository,
        push_config_repository: GoalPushConfigRepository,
        term_repository: GoalPriorityTermRepository,
    ) -> None:
        self.goal_repo = goal_repository
        self.push_config_repo = push_config_repository
        self.term_repo = term_repository

    async def build_goal_data(
        self,
        goal: Goal,
        push_config: GoalPushConfig | None = None,
        terms: list[GoalPriorityTerm] | None = None,
    ) -> GoalData:
        """Build goal data with config and terms.

        Args:
            goal: Goal entity
            push_config: Pre-fetched push config (if None, will fetch)
            terms: Pre-fetched terms (if None, will fetch)
        """
        # Fetch if not provided (for single goal queries)
        if push_config is None:
            push_config = await self.push_config_repo.get_by_goal_id(goal.id)
        if terms is None:
            terms = await self.term_repo.list_by_goal(goal.id)

        priority_terms = [t.term for t in terms if t.term_type == TermType.MUST]
        negative_terms = [t.term for t in terms if t.term_type == TermType.NEGATIVE]

        return GoalData(
            id=goal.id,
            name=goal.name,
            description=goal.description,
            priority_mode=goal.priority_mode,
            status=goal.status,
            priority_terms=priority_terms if priority_terms else None,
            negative_terms=negative_terms if negative_terms else None,
            batch_enabled=push_config.batch_enabled if push_config else None,
            batch_windows=push_config.batch_windows if push_config else None,
            digest_send_time=push_config.digest_send_time if push_config else None,
            stats=None,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
        )

    async def list_goals(
        self, user_id: str, status: str | None, page: int, page_size: int
    ) -> GoalListData:
        """List all goals for a user."""
        domain_status = GoalStatus(status) if status else None
        goals, total = await self.goal_repo.list_by_user(
            user_id=user_id,
            status=domain_status,
            page=page,
            page_size=page_size,
        )

        if not goals:
            return GoalListData(items=[], total=total, page=page, page_size=page_size)

        # Batch fetch push configs and terms to avoid N+1 queries
        goal_ids = [goal.id for goal in goals]
        push_configs_by_goal = await self.push_config_repo.get_by_goal_ids(goal_ids)
        terms_by_goal = await self.term_repo.list_by_goal_ids(goal_ids)

        items = [
            await self.build_goal_data(
                goal,
                push_config=push_configs_by_goal.get(goal.id),
                terms=terms_by_goal.get(goal.id, []),
            )
            for goal in goals
        ]

        return GoalListData(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_goal(self, goal_id: str, user_id: str) -> GoalData:
        """Get goal detail with access check."""
        goal = await self.goal_repo.get_by_id(goal_id)
        if not goal or goal.user_id != user_id:
            raise GoalNotFoundError(goal_id)

        return await self.build_goal_data(goal)
