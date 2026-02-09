"""API Key API routes.

Note: API Key management endpoints require JWT authentication only.
This prevents API keys from self-escalating their own permissions.
"""

from fastapi import APIRouter, Depends, status

from src.core.application.security import get_current_jwt_user_id
from src.core.interfaces.http.response import ApiResponse
from src.modules.api_keys.application.dependencies import get_api_key_service
from src.modules.api_keys.application.service import ApiKeyService
from src.modules.api_keys.domain.entities import ApiKey
from src.modules.api_keys.interfaces.schemas import (
    ApiKeyCreatedResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
    CreateApiKeyRequest,
)

router = APIRouter(prefix="/keys", tags=["api-keys"])


def _to_response(api_key: ApiKey) -> ApiKeyResponse:
    """Convert domain entity to response schema."""
    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        is_active=api_key.is_active,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
    )


@router.post(
    "",
    response_model=ApiResponse[ApiKeyCreatedResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建 API Key",
    description="创建新的 API Key。返回的 raw_key 仅此一次展示，请立即复制保存。",
)
async def create_api_key(
    request: CreateApiKeyRequest,
    user_id: str = Depends(get_current_jwt_user_id),
    service: ApiKeyService = Depends(get_api_key_service),
) -> ApiResponse[ApiKeyCreatedResponse]:
    """Create a new API key."""
    api_key, raw_key = await service.create_key(
        user_id=user_id,
        name=request.name,
        scopes=[s.value for s in request.scopes],
        expires_in_days=request.expires_in_days,
    )
    return ApiResponse.success(
        data=ApiKeyCreatedResponse(
            key=_to_response(api_key),
            raw_key=raw_key,
        ),
        message="API Key created successfully",
        code=status.HTTP_201_CREATED,
    )


@router.get(
    "",
    response_model=ApiResponse[ApiKeyListResponse],
    summary="列出 API Keys",
    description="列出当前用户的所有 API Keys。",
)
async def list_api_keys(
    user_id: str = Depends(get_current_jwt_user_id),
    service: ApiKeyService = Depends(get_api_key_service),
) -> ApiResponse[ApiKeyListResponse]:
    """List all API keys for the current user."""
    keys = await service.list_keys(user_id)
    return ApiResponse.success(
        data=ApiKeyListResponse(
            keys=[_to_response(k) for k in keys],
            total=len(keys),
        )
    )


@router.delete(
    "/{key_id}",
    response_model=ApiResponse[ApiKeyResponse],
    summary="撤销 API Key",
    description="撤销指定的 API Key，撤销后不可恢复。",
)
async def revoke_api_key(
    key_id: str,
    user_id: str = Depends(get_current_jwt_user_id),
    service: ApiKeyService = Depends(get_api_key_service),
) -> ApiResponse[ApiKeyResponse]:
    """Revoke an API key."""
    revoked = await service.revoke_key(user_id=user_id, key_id=key_id)
    return ApiResponse.success(
        data=_to_response(revoked),
        message="API Key revoked successfully",
    )


@router.post(
    "/{key_id}/rotate",
    response_model=ApiResponse[ApiKeyCreatedResponse],
    summary="轮换 API Key",
    description="轮换指定的 API Key：生成新 Key 并撤销旧 Key。操作在同一事务内完成。",
)
async def rotate_api_key(
    key_id: str,
    user_id: str = Depends(get_current_jwt_user_id),
    service: ApiKeyService = Depends(get_api_key_service),
) -> ApiResponse[ApiKeyCreatedResponse]:
    """Rotate an API key (create new, revoke old)."""
    new_key, raw_key = await service.rotate_key(user_id=user_id, key_id=key_id)
    return ApiResponse.success(
        data=ApiKeyCreatedResponse(
            key=_to_response(new_key),
            raw_key=raw_key,
        ),
        message="API Key rotated successfully",
    )
