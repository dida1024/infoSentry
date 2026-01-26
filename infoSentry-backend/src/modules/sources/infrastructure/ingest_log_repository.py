"""IngestLog 仓储实现。"""

from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from src.modules.sources.application.ingest_service import IngestResult
from src.modules.sources.infrastructure.models import IngestLogModel, IngestStatus


class IngestLogRepository:
    """IngestLog 仓储。

    用于记录每次抓取的详细信息，便于监控和排查问题。
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_from_result(
        self,
        result: IngestResult,
        started_at: datetime,
    ) -> IngestLogModel:
        """从 IngestResult 创建日志记录。

        Args:
            result: 抓取结果
            started_at: 开始时间

        Returns:
            创建的日志记录
        """
        log = IngestLogModel(
            source_id=result.source_id,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            status=result.status,
            items_fetched=result.items_fetched,
            items_new=result.items_new,
            items_duplicate=result.items_duplicate,
            error_message=result.error_message,
            duration_ms=result.duration_ms,
            metadata_json={
                "new_item_ids": result.new_item_ids[:10] if result.new_item_ids else [],
            },
        )

        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def get_by_id(self, log_id: str) -> IngestLogModel | None:
        """根据 ID 获取日志。"""
        statement = select(IngestLogModel).where(
            IngestLogModel.id == log_id,
            col(IngestLogModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_source(
        self,
        source_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[IngestLogModel], int]:
        """列出某个源的抓取日志。"""
        statement = (
            select(
                IngestLogModel,
                func.count(IngestLogModel.id).over().label("total_count"),
            )
            .where(
                IngestLogModel.source_id == source_id,
                col(IngestLogModel.is_deleted).is_(False),
            )
            .order_by(IngestLogModel.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        logs = [row.IngestLogModel for row in rows]
        return logs, total_count

    async def list_recent_errors(
        self,
        limit: int = 50,
    ) -> list[IngestLogModel]:
        """列出最近的错误日志。"""
        statement = (
            select(IngestLogModel)
            .where(
                IngestLogModel.status == IngestStatus.FAILED,
                col(IngestLogModel.is_deleted).is_(False),
            )
            .order_by(IngestLogModel.started_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_source_stats(
        self,
        source_id: str,
        since: datetime | None = None,
    ) -> dict:
        """获取源的统计信息。"""
        statement = select(
            func.count(IngestLogModel.id).label("total_runs"),
            func.sum(IngestLogModel.items_fetched).label("total_fetched"),
            func.sum(IngestLogModel.items_new).label("total_new"),
            func.avg(IngestLogModel.duration_ms).label("avg_duration_ms"),
        ).where(
            IngestLogModel.source_id == source_id,
            col(IngestLogModel.is_deleted).is_(False),
        )

        if since:
            statement = statement.where(IngestLogModel.started_at >= since)

        result = await self.session.execute(statement)
        row = result.one()

        return {
            "total_runs": row.total_runs or 0,
            "total_fetched": row.total_fetched or 0,
            "total_new": row.total_new or 0,
            "avg_duration_ms": int(row.avg_duration_ms or 0),
        }

    async def count_errors_since(
        self,
        source_id: str,
        since: datetime,
    ) -> int:
        """统计某个时间以来的错误次数。"""
        statement = select(func.count(IngestLogModel.id)).where(
            IngestLogModel.source_id == source_id,
            IngestLogModel.status == IngestStatus.FAILED,
            IngestLogModel.started_at >= since,
            col(IngestLogModel.is_deleted).is_(False),
        )

        result = await self.session.execute(statement)
        return result.scalar() or 0
