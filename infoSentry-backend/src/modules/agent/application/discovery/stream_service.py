"""Discovery SSE streaming service — runs the agent and yields SSE events."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from loguru import logger
from pydantic_ai import (
    AgentRunResultEvent,
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPartDelta,
)

from src.core.config import settings
from src.core.infrastructure.logging import get_business_logger
from src.modules.agent.application.discovery.agent import (
    DiscoveryDeps,
    FetcherCreator,
    get_discovery_agent,
)
from src.modules.agent.domain.discovery_entities import (
    DiscoverySession,
    MessageRole,
    SessionStatus,
)
from src.modules.agent.domain.repository import (
    DiscoveryCandidateRepository,
    DiscoverySessionRepository,
)
from src.modules.sources.application.handlers import (
    CreateSourceHandler,
    SubscribeSourceHandler,
)
from src.modules.sources.application.services import SourceQueryService
from src.modules.sources.domain.catalog import NewsNowCatalogProvider
from src.modules.sources.domain.repository import SourceRepository


def _sse_event(event: str, data: dict[str, Any]) -> dict[str, Any]:
    """Format an SSE event dict for sse-starlette."""
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


async def run_discovery_stream(
    session: DiscoverySession,
    session_repo: DiscoverySessionRepository,
    candidate_repo: DiscoveryCandidateRepository,
    source_repository: SourceRepository,
    catalog_provider: NewsNowCatalogProvider,
    create_source_handler: CreateSourceHandler,
    subscribe_source_handler: SubscribeSourceHandler,
    source_query_service: SourceQueryService,
    create_fetcher: FetcherCreator,
) -> AsyncGenerator[dict[str, Any], None]:
    """Run the discovery agent and yield SSE events.

    This is the core streaming function called by the SSE endpoint.
    Handles LLM retry (1x), tool call budget, and graceful error recovery.
    """
    agent = get_discovery_agent()
    start_time = time.monotonic()
    log = logger.bind(session_id=session.id, user_id=session.user_id)
    # Build message history from session for the agent
    message_history_text = "\n".join(
        f"{'用户' if m.role == MessageRole.USER else 'Agent'}: {m.content}"
        for m in session.messages
    )

    user_messages = [m for m in session.messages if m.role == MessageRole.USER]
    if not user_messages:
        yield _sse_event("error", {"message": "没有用户消息"})
        return

    prompt = user_messages[-1].content

    async with httpx.AsyncClient(
        timeout=settings.DISCOVERY_PROBE_TIMEOUT_SEC
    ) as http_client:
        deps = DiscoveryDeps(
            catalog_provider=catalog_provider,
            create_fetcher=create_fetcher,
            create_source_handler=create_source_handler,
            subscribe_source_handler=subscribe_source_handler,
            source_query_service=source_query_service,
            source_repository=source_repository,
            candidate_repository=candidate_repo,
            http_client=http_client,
            session=session,
            rsshub_base_url=settings.RSSHUB_BASE_URL,
            probe_timeout=settings.DISCOVERY_PROBE_TIMEOUT_SEC,
            web_search_api_key=settings.DISCOVERY_WEB_SEARCH_API_KEY,
        )

        accumulated_text = ""
        tool_call_count = 0
        # Track explicit business events from tool results
        has_valid_candidates = False
        source_added = False

        if len(session.messages) > 1:
            prompt = f"对话历史:\n{message_history_text}\n\n请根据对话历史继续。"

        # LLM retry: attempt up to 2 times
        max_attempts = 2
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                async for event in agent.run_stream_events(prompt, deps=deps):
                    if isinstance(event, AgentRunResultEvent):
                        final_text = event.result.output
                        if final_text and final_text != accumulated_text:
                            yield _sse_event("agent_message", {"content": final_text})
                            accumulated_text = final_text

                    elif isinstance(event, PartStartEvent):
                        pass

                    elif isinstance(event, PartDeltaEvent):
                        if isinstance(event.delta, TextPartDelta):
                            delta = event.delta.content_delta
                            if delta:
                                accumulated_text += delta
                                yield _sse_event(
                                    "agent_message", {"content": delta, "delta": True}
                                )

                    elif isinstance(event, FunctionToolCallEvent):
                        tool_call_count += 1
                        tool_name = event.part.tool_name
                        log.debug("Tool call", tool=tool_name, count=tool_call_count)

                        if tool_call_count > settings.DISCOVERY_AGENT_MAX_TOOL_CALLS:
                            log.warning(
                                "Tool call limit exceeded",
                                limit=settings.DISCOVERY_AGENT_MAX_TOOL_CALLS,
                            )
                            yield _sse_event(
                                "error",
                                {
                                    "message": f"工具调用次数超限 ({settings.DISCOVERY_AGENT_MAX_TOOL_CALLS})",
                                    "recoverable": False,
                                },
                            )
                            break

                        try:
                            args = (
                                json.loads(event.part.args)
                                if isinstance(event.part.args, str)
                                else event.part.args
                            )
                        except (json.JSONDecodeError, TypeError):
                            args = str(event.part.args)

                        yield _sse_event("tool_call", {"tool": tool_name, "args": args})

                    elif isinstance(event, FunctionToolResultEvent):
                        content = event.content
                        summary = str(content)[:500] if content else ""
                        tool_id = event.tool_call_id or ""
                        yield _sse_event(
                            "tool_result", {"tool_call_id": tool_id, "summary": summary}
                        )

                        # Track business events via structured _signal field
                        # Tools return {"_signal": "candidates_valid"} or {"_signal": "source_added"}
                        if isinstance(content, dict):
                            signal = content.get("_signal")
                        elif isinstance(content, str):
                            try:
                                parsed_content = json.loads(content)
                                signal = (
                                    parsed_content.get("_signal")
                                    if isinstance(parsed_content, dict)
                                    else None
                                )
                            except (json.JSONDecodeError, TypeError):
                                signal = None
                        else:
                            signal = None

                        if signal == "candidates_valid":
                            has_valid_candidates = True
                        elif signal == "source_added":
                            source_added = True

                    elif isinstance(event, FinalResultEvent):
                        pass

                # Success — break retry loop
                last_error = None
                break

            except Exception as e:
                last_error = e
                if attempt < max_attempts:
                    log.warning(
                        "Agent attempt failed, retrying",
                        attempt=attempt,
                        error=str(e),
                    )
                    yield _sse_event(
                        "agent_message",
                        {
                            "content": "正在重试...",
                            "delta": True,
                        },
                    )
                    continue
                # Final attempt failed
                break

        duration_ms = int((time.monotonic() - start_time) * 1000)

        if last_error is not None:
            log.error(
                "Discovery agent failed after retries",
                error=str(last_error),
                duration_ms=duration_ms,
                tool_calls=tool_call_count,
            )
            get_business_logger().error(
                "discovery_turn_failed",
                session_id=session.id,
                user_id=session.user_id,
                error_type=type(last_error).__name__,
                error=str(last_error),
                duration_ms=duration_ms,
                tool_calls=tool_call_count,
            )
            session.add_message(
                MessageRole.SYSTEM,
                f"Agent 执行出错: {type(last_error).__name__}",
            )
            try:
                session.transition_to(SessionStatus.FAILED)
            except ValueError:
                pass
            await session_repo.update(session)
            yield _sse_event(
                "error",
                {
                    "message": f"Agent 执行出错: {type(last_error).__name__}",
                    "recoverable": False,
                },
            )
            return

        # Turn complete — save agent response
        if accumulated_text:
            session.add_message(MessageRole.AGENT, accumulated_text)

        # Determine next state based on explicit tool results, not text heuristics
        if source_added:
            # add_source succeeded → session complete
            session.transition_to(SessionStatus.COMPLETED)
            await session_repo.update(session)
            get_business_logger().info(
                "discovery_session_completed",
                session_id=session.id,
                user_id=session.user_id,
                duration_ms=duration_ms,
                tool_calls=tool_call_count,
            )
            yield _sse_event("session_completed", {"message": "发现会话已完成"})
        elif has_valid_candidates:
            # validate_source found valid candidates → wait for user confirmation
            session.transition_to(SessionStatus.WAITING_USER)
            await session_repo.update(session)
            get_business_logger().info(
                "discovery_confirmation_requested",
                session_id=session.id,
                user_id=session.user_id,
                duration_ms=duration_ms,
                tool_calls=tool_call_count,
            )
            yield _sse_event("confirm_required", {"message": "Agent 等待你的确认"})
        else:
            # No decisive action — save state and let SSE close naturally
            await session_repo.update(session)

        log.info(
            "Discovery turn complete",
            duration_ms=duration_ms,
            tool_calls=tool_call_count,
            text_length=len(accumulated_text),
            final_status=session.status.value,
        )
