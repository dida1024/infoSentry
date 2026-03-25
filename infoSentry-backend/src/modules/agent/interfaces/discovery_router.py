"""Discovery API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sse_starlette.sse import EventSourceResponse

from src.core.application.security import get_current_user_id
from src.core.domain.exceptions import DuplicateEntityError
from src.core.interfaces.http.response import ApiResponse, PaginatedResponse
from src.modules.agent.application.discovery.agent import FetcherCreator
from src.modules.agent.application.discovery.dependencies import (
    get_catalog_provider,
    get_discovery_candidate_repository,
    get_discovery_session_repository,
    get_discovery_session_service,
    get_fetcher_creator,
)
from src.modules.agent.application.discovery.session_service import (
    DiscoverySessionService,
)
from src.modules.agent.application.discovery.stream_service import (
    run_discovery_stream,
)
from src.modules.agent.domain.discovery_entities import (
    CandidateSource,
    DiscoverySession,
    SessionStatus,
)
from src.modules.agent.domain.repository import (
    DiscoveryCandidateRepository,
    DiscoverySessionRepository,
)
from src.modules.agent.interfaces.discovery_schemas import (
    CandidateResponse,
    CreateSessionRequest,
    SendMessageRequest,
    SessionListItemResponse,
    SessionMessageResponse,
    SessionResponse,
)
from src.modules.sources.application.dependencies import (
    get_create_source_handler,
    get_source_query_service,
    get_source_repository,
    get_subscribe_source_handler,
)
from src.modules.sources.application.handlers import (
    CreateSourceHandler,
    SubscribeSourceHandler,
)
from src.modules.sources.application.services import SourceQueryService
from src.modules.sources.domain.catalog import NewsNowCatalogProvider
from src.modules.sources.domain.repository import SourceRepository

router = APIRouter(prefix="/discovery", tags=["discovery"])


def _to_session_response(
    session: DiscoverySession,
    candidates: list[CandidateSource] | None = None,
) -> SessionResponse:
    messages = [
        SessionMessageResponse(
            role=m.role.value,
            content=m.content,
            timestamp=m.created_at,
            metadata=m.metadata,
        )
        for m in session.messages
    ]
    candidate_list = [
        CandidateResponse(
            id=c.id,
            source_type=c.source_type,
            name=c.name,
            url=c.url,
            status=c.status.value,
            discovered_via=c.discovered_via,
            validation_result=c.validation_result,
            source_id=c.source_id,
        )
        for c in (candidates or [])
    ]
    return SessionResponse(
        id=session.id,
        status=session.status.value,
        initial_query=session.initial_query,
        messages=messages,
        candidates=candidate_list,
        created_at=session.created_at,
        updated_at=session.updated_at,
        expires_at=session.expires_at,
    )


@router.post(
    "/sessions",
    response_model=ApiResponse[SessionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    request: CreateSessionRequest,
    user_id: str = Depends(get_current_user_id),
    service: DiscoverySessionService = Depends(get_discovery_session_service),
) -> ApiResponse[SessionResponse]:
    """Create a new source discovery session."""
    try:
        session = await service.create_session(user_id, request.query)
    except (ValueError, DuplicateEntityError) as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    return ApiResponse.success(data=_to_session_response(session))


@router.get(
    "/sessions/{session_id}",
    response_model=ApiResponse[SessionResponse],
)
async def get_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    service: DiscoverySessionService = Depends(get_discovery_session_service),
    candidate_repo: DiscoveryCandidateRepository = Depends(
        get_discovery_candidate_repository
    ),
) -> ApiResponse[SessionResponse]:
    """Get session detail with full message history (for reconnection)."""
    session = await service.get_session(session_id, user_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    candidates = await candidate_repo.list_by_session(session_id)
    return ApiResponse.success(data=_to_session_response(session, candidates))


@router.get(
    "/sessions/{session_id}/stream",
)
async def stream_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    service: DiscoverySessionService = Depends(get_discovery_session_service),
    session_repo: DiscoverySessionRepository = Depends(
        get_discovery_session_repository
    ),
    candidate_repo: DiscoveryCandidateRepository = Depends(
        get_discovery_candidate_repository
    ),
    source_repository: SourceRepository = Depends(get_source_repository),
    create_source_handler: CreateSourceHandler = Depends(get_create_source_handler),
    subscribe_source_handler: SubscribeSourceHandler = Depends(
        get_subscribe_source_handler
    ),
    source_query_service: SourceQueryService = Depends(get_source_query_service),
    catalog_provider: NewsNowCatalogProvider = Depends(get_catalog_provider),
    create_fetcher: FetcherCreator = Depends(get_fetcher_creator),
) -> EventSourceResponse:
    """SSE stream for agent output.

    Streams agent thinking, tool calls, and results in real-time.
    The stream closes when the agent needs user confirmation or completes.
    """
    session = await service.get_session(session_id, user_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Only stream for active sessions
    if session.status not in (SessionStatus.ACTIVE, SessionStatus.WAITING_USER):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is in terminal state: {session.status.value}",
        )

    return EventSourceResponse(
        run_discovery_stream(
            session=session,
            session_repo=session_repo,
            candidate_repo=candidate_repo,
            source_repository=source_repository,
            catalog_provider=catalog_provider,
            create_source_handler=create_source_handler,
            subscribe_source_handler=subscribe_source_handler,
            source_query_service=source_query_service,
            create_fetcher=create_fetcher,
        ),
        media_type="text/event-stream",
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ApiResponse[SessionResponse],
)
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    user_id: str = Depends(get_current_user_id),
    service: DiscoverySessionService = Depends(get_discovery_session_service),
) -> ApiResponse[SessionResponse]:
    """Send a user message (confirmation or follow-up)."""
    try:
        session = await service.add_user_message(session_id, user_id, request.content)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return ApiResponse.success(data=_to_session_response(session))


@router.get(
    "/sessions",
    response_model=PaginatedResponse[SessionListItemResponse],
)
async def list_sessions(
    user_id: str = Depends(get_current_user_id),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: DiscoverySessionService = Depends(get_discovery_session_service),
) -> PaginatedResponse[SessionListItemResponse]:
    """List discovery sessions for the current user."""
    sessions, total = await service.list_sessions(user_id, page, page_size)
    items = [
        SessionListItemResponse(
            id=s.id,
            status=s.status.value,
            initial_query=s.initial_query,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]
    return PaginatedResponse.create(items, total, page, page_size)
