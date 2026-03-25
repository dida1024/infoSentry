"""Tool: add_source — add a validated source to the system (requires user confirmation)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger
from pydantic_ai import RunContext

from src.core.infrastructure.logging import get_business_logger
from src.modules.sources.application.commands import (
    CreateSourceCommand,
    SubscribeSourceCommand,
)
from src.modules.sources.domain.entities import SourceType

if TYPE_CHECKING:
    from src.modules.agent.application.discovery.agent import DiscoveryDeps


async def add_source(
    ctx: RunContext[DiscoveryDeps],
    name: str,
    source_type: str,
    config: dict[str, Any],
    candidate_id: str | None = None,
) -> dict[str, Any]:
    """将验证通过的信息源添加到系统。只能在用户明确确认后调用。

    Args:
        name: 源名称（人类可读），如 "深圳住建局公告"
        source_type: 源类型，"RSS" / "SITE" / "NEWSNOW"
        config: 完整的源配置
        candidate_id: validate_source 返回的 candidate_id（用于更新候选状态）
    """
    session = ctx.deps.session
    try:
        st = SourceType(source_type)
    except ValueError:
        return {"success": False, "error": f"不支持的源类型: {source_type}"}

    # Dedup checks
    config_url_map = {
        SourceType.RSS: "feed_url",
        SourceType.SITE: "list_url",
        SourceType.NEWSNOW: "source_id",
    }
    config_key = config_url_map.get(st)
    config_url = config.get(config_key, "") if config_key else ""

    try:
        name_exists = await ctx.deps.source_repository.exists_by_name(name)
        if name_exists:
            return {"success": False, "error": f"名称 '{name}' 已存在"}

        if config_url:
            url_exists = await ctx.deps.source_repository.exists_by_config_url(
                st, config_url
            )
            if url_exists:
                return {
                    "success": False,
                    "error": f"该源的配置 URL 已存在: {config_url}",
                }
    except Exception as e:
        logger.warning(f"add_source dedup check failed: {e}")
        return {"success": False, "error": f"查重检查失败: {e}"}

    # Create source
    try:
        cmd = CreateSourceCommand(
            user_id=session.user_id,
            type=st,
            name=name,
            config=config,
            is_private=False,
        )
        source = await ctx.deps.create_source_handler.handle(cmd)
    except Exception as e:
        logger.error(f"add_source create failed: {e}")
        return {"success": False, "error": f"创建源失败: {e}"}

    # Subscribe user — compensate on failure by deleting source
    try:
        sub_cmd = SubscribeSourceCommand(
            source_id=source.id,
            user_id=session.user_id,
        )
        await ctx.deps.subscribe_source_handler.handle(sub_cmd)
    except Exception as e:
        logger.error(f"add_source subscribe failed, compensating: {e}")
        get_business_logger().warning(
            "discovery_source_subscribe_failed",
            session_id=session.id,
            user_id=session.user_id,
            source_name=name,
            source_type=source_type,
            error_type=type(e).__name__,
            error=str(e),
        )
        try:
            await ctx.deps.source_repository.delete(source)
        except Exception as del_err:
            logger.error(f"Compensation (delete source) also failed: {del_err}")
            get_business_logger().error(
                "discovery_source_compensation_failed",
                session_id=session.id,
                user_id=session.user_id,
                source_id=source.id,
                stage="subscribe_failure",
                error_type=type(del_err).__name__,
                error=str(del_err),
            )
        return {"success": False, "error": f"订阅失败（源已回滚）: {e}"}

    # Update candidate status to ACCEPTED — must succeed for overall success
    if candidate_id:
        try:
            candidate = await ctx.deps.candidate_repository.get_by_id(candidate_id)
            if candidate is None:
                raise ValueError(f"候选不存在: {candidate_id}")
            candidate.accept(source.id)
            await ctx.deps.candidate_repository.update(candidate)
        except Exception as e:
            logger.error(f"Candidate accept failed, compensating: {e}")
            get_business_logger().warning(
                "discovery_candidate_accept_failed",
                session_id=session.id,
                user_id=session.user_id,
                source_id=source.id,
                candidate_id=candidate_id,
                error_type=type(e).__name__,
                error=str(e),
            )
            try:
                await ctx.deps.source_repository.delete(source)
            except Exception as del_err:
                logger.error(
                    f"Compensation (delete source after candidate fail) also failed: {del_err}"
                )
                get_business_logger().error(
                    "discovery_source_compensation_failed",
                    session_id=session.id,
                    user_id=session.user_id,
                    source_id=source.id,
                    stage="candidate_accept_failure",
                    error_type=type(del_err).__name__,
                    error=str(del_err),
                )
            return {"success": False, "error": f"候选状态更新失败（源已回滚）: {e}"}

    get_business_logger().info(
        "discovery_source_added",
        session_id=session.id,
        user_id=session.user_id,
        source_id=source.id,
        source_name=name,
        source_type=source_type,
        candidate_id=candidate_id,
    )
    return {"success": True, "source_id": source.id, "_signal": "source_added"}
