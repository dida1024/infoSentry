"""Discovery session entity-model mappers."""

from src.core.infrastructure.database.mapper import BaseMapper
from src.modules.agent.domain.discovery_entities import (
    CandidateSource,
    CandidateStatus,
    DiscoverySession,
    SessionMessage,
    SessionStatus,
)
from src.modules.agent.infrastructure.discovery.models import (
    DiscoveryCandidateModel,
    DiscoverySessionModel,
)


class DiscoverySessionMapper(BaseMapper[DiscoverySession, DiscoverySessionModel]):
    """Discovery session entity-model mapper."""

    def to_domain(self, model: DiscoverySessionModel) -> DiscoverySession:
        messages: list[SessionMessage] = []
        if model.messages_json:
            raw_messages = model.messages_json.get("messages", [])
            for raw in raw_messages:
                messages.append(SessionMessage(**raw))

        return DiscoverySession(
            id=model.id,
            user_id=model.user_id,
            status=SessionStatus(model.status),
            initial_query=model.initial_query,
            messages=messages,
            expires_at=model.expires_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: DiscoverySession) -> DiscoverySessionModel:
        messages_json = {
            "messages": [msg.model_dump(mode="json") for msg in entity.messages]
        }

        return DiscoverySessionModel(
            id=entity.id,
            user_id=entity.user_id,
            status=entity.status.value,
            initial_query=entity.initial_query,
            messages_json=messages_json,
            expires_at=entity.expires_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )


class DiscoveryCandidateMapper(BaseMapper[CandidateSource, DiscoveryCandidateModel]):
    """Discovery candidate entity-model mapper."""

    def to_domain(self, model: DiscoveryCandidateModel) -> CandidateSource:
        return CandidateSource(
            id=model.id,
            session_id=model.session_id,
            source_type=model.source_type,
            name=model.name,
            url=model.url,
            config=model.config_json or {},
            status=CandidateStatus(model.status),
            validation_result=model.validation_result_json,
            discovered_via=model.discovered_via,
            source_id=model.source_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: CandidateSource) -> DiscoveryCandidateModel:
        return DiscoveryCandidateModel(
            id=entity.id,
            session_id=entity.session_id,
            source_type=entity.source_type,
            name=entity.name,
            url=entity.url,
            config_json=entity.config,
            status=entity.status.value,
            validation_result_json=entity.validation_result,
            discovered_via=entity.discovered_via,
            source_id=entity.source_id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )
