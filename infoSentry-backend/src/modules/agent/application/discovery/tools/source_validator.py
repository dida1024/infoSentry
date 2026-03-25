"""Tool: validate_source — validate a source config by actually fetching it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger
from pydantic_ai import RunContext

from src.core.infrastructure.logging import get_business_logger
from src.modules.agent.domain.discovery_entities import CandidateSource, CandidateStatus
from src.modules.sources.domain.entities import SourceType

if TYPE_CHECKING:
    from src.modules.agent.application.discovery.agent import DiscoveryDeps


async def validate_source(
    ctx: RunContext[DiscoveryDeps],
    name: str,
    source_type: str,
    config: dict[str, Any],
    url: str,
    discovered_via: str = "unknown",
) -> dict[str, Any]:
    """验证信息源配置是否可用。

    实际创建 Fetcher 并执行一次抓取，确认能连通且有数据返回。
    同时创建并持久化 CandidateSource 记录。

    Args:
        name: 候选源名称
        source_type: 源类型，"RSS" / "SITE" / "NEWSNOW"
        config: 源配置，如 {"feed_url": "https://example.com/rss"}
        url: 候选源主 URL
        discovered_via: 发现渠道 (catalog/rss_probe/rsshub/site_analysis)
    """
    try:
        st = SourceType(source_type)
    except ValueError:
        return {"valid": False, "error": f"不支持的源类型: {source_type}"}

    # Create candidate record (DISCOVERED → VALIDATING)
    candidate = CandidateSource(
        session_id=ctx.deps.session.id,
        source_type=source_type,
        name=name,
        url=url,
        config=config,
        status=CandidateStatus.DISCOVERED,
        discovered_via=discovered_via,
    )
    candidate.status = CandidateStatus.VALIDATING
    try:
        candidate = await ctx.deps.candidate_repository.create(candidate)
    except Exception as e:
        logger.warning(f"Failed to persist candidate: {e}")
        get_business_logger().warning(
            "discovery_candidate_persist_failed",
            session_id=ctx.deps.session.id,
            user_id=ctx.deps.session.user_id,
            candidate_name=name,
            candidate_url=url,
            error_type=type(e).__name__,
            error=str(e),
        )
        return {"valid": False, "error": f"候选持久化失败: {type(e).__name__}"}

    try:
        fetcher = ctx.deps.create_fetcher(st, config)
    except ValueError as e:
        update_ok = await _mark_candidate(
            ctx, candidate, valid=False, result={"error": str(e)}
        )
        if not update_ok:
            return {"valid": False, "error": "候选状态更新失败: fetcher_create"}
        return {"valid": False, "error": f"无法创建 fetcher: {e}"}

    is_valid, error_msg = fetcher.validate_config()
    if not is_valid:
        update_ok = await _mark_candidate(
            ctx, candidate, valid=False, result={"error": error_msg}
        )
        if not update_ok:
            return {"valid": False, "error": "候选状态更新失败: invalid_config"}
        return {"valid": False, "error": f"配置无效: {error_msg}"}

    try:
        result = await fetcher.fetch()
    except Exception as e:
        logger.warning(f"validate_source fetch failed: {e}")
        update_ok = await _mark_candidate(
            ctx, candidate, valid=False, result={"error": str(e)}
        )
        if not update_ok:
            return {"valid": False, "error": "候选状态更新失败: fetch_failed"}
        return {"valid": False, "error": f"抓取失败: {type(e).__name__}: {e}"}

    if result.is_success and result.items:
        sample_titles = [item.title for item in result.items[:5]]
        validation_result = {
            "valid": True,
            "status": result.status.value,
            "items_count": len(result.items),
            "sample_titles": sample_titles,
        }
        update_ok = await _mark_candidate(
            ctx, candidate, valid=True, result=validation_result
        )
        if not update_ok:
            return {"valid": False, "error": "候选状态更新失败: validation_success"}
        return {**validation_result, "candidate_id": candidate.id, "_signal": "candidates_valid"}
    else:
        validation_result = {
            "valid": False,
            "status": result.status.value,
            "items_count": len(result.items),
            "error": result.error_message or "未获取到内容",
        }
        update_ok = await _mark_candidate(
            ctx, candidate, valid=False, result=validation_result
        )
        if not update_ok:
            return {"valid": False, "error": "候选状态更新失败: validation_failed"}
        return validation_result


async def _mark_candidate(
    ctx: RunContext[DiscoveryDeps],
    candidate: CandidateSource,
    *,
    valid: bool,
    result: dict[str, Any],
) -> bool:
    """Update candidate status after validation."""
    try:
        if valid:
            candidate.mark_valid(result)
        else:
            candidate.mark_invalid(result)
        await ctx.deps.candidate_repository.update(candidate)
        return True
    except Exception as e:
        logger.warning(f"Failed to update candidate status: {e}")
        get_business_logger().warning(
            "discovery_candidate_update_failed",
            session_id=ctx.deps.session.id,
            user_id=ctx.deps.session.user_id,
            candidate_id=candidate.id,
            candidate_status=candidate.status.value,
            error_type=type(e).__name__,
            error=str(e),
        )
        return False
