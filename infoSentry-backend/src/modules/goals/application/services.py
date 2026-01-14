"""Goal application services."""

from loguru import logger

from src.modules.goals.application.models import (
    GoalMatchData,
    GoalMatchListData,
    ItemData,
)
from src.modules.goals.domain.exceptions import GoalNotFoundError
from src.modules.goals.domain.repository import GoalRepository
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
        page: int = 1,
        page_size: int = 20,
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
        self.logger.info(f"Listing matches for goal {goal_id} for user {user_id} with min_score {min_score} and page {page} and page_size {page_size}")
        # Access check
        goal = await self.goal_repo.get_by_id(goal_id)
        if not goal or goal.user_id != user_id:
            raise GoalNotFoundError(goal_id)

        # Query matches
        matches, total = await self.match_repo.list_by_goal(
            goal_id=goal_id,
            min_score=min_score,
            page=page,
            page_size=page_size,
        )

        if not matches:
            self.logger.info(f"No matches found for goal {goal_id} for user {user_id} with min_score {min_score} and page {page} and page_size {page_size}")
            return GoalMatchListData(
                items=[],
                total=total,
                page=page,
                page_size=page_size,
            )

        # Batch fetch items and sources
        items_map: dict[str, ItemData] = {}
        for match in matches:
            item = await self.item_repo.get_by_id(match.item_id)
            if item:
                source = await self.source_repo.get_by_id(item.source_id)
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
            for match in matches
        ]
        self.logger.info(f"Found {len(match_items)} matches for goal {goal_id} for user {user_id} with min_score {min_score} and page {page} and page_size {page_size}")
        return GoalMatchListData(
            items=match_items,
            total=total,
            page=page,
            page_size=page_size,
        )
