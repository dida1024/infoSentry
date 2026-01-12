"""JWT token handling."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from pydantic import BaseModel, Field

from src.core.config import settings

security = HTTPBearer()


class TokenPayload(BaseModel):
    """JWT Token Payload 结构。"""

    sub: str = Field(..., description="Subject (用户ID或email)")
    exp: int = Field(..., description="过期时间戳", gt=0)
    token_type: str | None = Field(None, description="Token 类型 (如 'magic_link')")

    def get_subject(self) -> str:
        """获取 subject (用户ID/email)。"""
        return self.sub

    def is_magic_link(self) -> bool:
        """是否为 magic link token。"""
        return self.token_type == "magic_link"



def create_access_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
    extra_claims: dict | None = None,
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {"exp": expire, "sub": str(subject)}
    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenPayload: 解码后的 token payload

    Raises:
        HTTPException: Token 过期或无效
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        # Pydantic 自动验证和转换
        return TokenPayload(
            sub=payload.get("sub", ""),
            exp=payload.get("exp", 0),
            token_type=payload.get("type"),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Get current user ID from JWT token.

    Args:
        credentials: HTTP Bearer token

    Returns:
        str: 用户 ID

    Raises:
        HTTPException: Token 无效或缺少用户ID
    """
    payload = decode_token(credentials.credentials)
    user_id = payload.get_subject()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return user_id


def create_magic_link_token(email: str) -> str:
    """Create a magic link token for email authentication."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.MAGIC_LINK_EXPIRE_MINUTES)
    to_encode = {
        "exp": expire,
        "sub": email,
        "type": "magic_link",
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_magic_link_token(token: str) -> str:
    """Decode and validate a magic link token.

    Args:
        token: Magic link JWT token

    Returns:
        str: Email 地址

    Raises:
        HTTPException: Token 无效、过期或类型错误
    """
    try:
        payload = decode_token(token)

        if not payload.is_magic_link():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid magic link token",
            )

        email = payload.get_subject()
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid magic link token",
            )
        return email
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Magic link has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid magic link token",
        )


class JWTTokenService:
    """Token service implementation using JWT."""

    def create_access_token(self, subject: str, extra_claims: dict | None = None) -> str:
        return create_access_token(subject=subject, extra_claims=extra_claims)

    def create_magic_link_token(self, email: str) -> str:
        return create_magic_link_token(email)


def get_token_service() -> JWTTokenService:
    """Get token service instance."""
    return JWTTokenService()
