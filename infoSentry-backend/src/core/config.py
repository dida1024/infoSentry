"""Application configuration."""

import secrets
import warnings
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    computed_field,
    model_validator,
)
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    # Application
    PROJECT_NAME: str = "infoSentry"
    SERVER_PORT: int = 8000
    ROOTPATH: str = ""
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    MAGIC_LINK_EXPIRE_MINUTES: int = 30  # Magic link 30分钟过期
    FRONTEND_HOST: str = "http://localhost:3000"
    BACKEND_HOST: str = "http://localhost:8000"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    LOG_LEVEL: str = "INFO"
    JWT_ALGORITHM: str = "HS256"
    TIMEZONE: str = "Asia/Shanghai"

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    # Sentry
    SENTRY_DSN: HttpUrl | None = None

    # PostgreSQL
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "infosentry"

    @computed_field
    @property
    def database_url_object(self) -> MultiHostUrl:
        return MultiHostUrl.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return str(self.database_url_object)

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # SMTP
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    # OpenAI
    OPENAI_API_KEY: str | None = None
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    OPENAI_EMBED_MODEL: str = "text-embedding-3-small"
    OPENAI_JUDGE_MODEL: str = "gpt-4o-mini"
    EMBEDDING_DIMENSION: int = 1536

    # Feature Flags（降级开关）
    LLM_ENABLED: bool = True  # 关闭后边界判别全部降级 Batch
    EMBEDDING_ENABLED: bool = True  # 关闭后 embedding 跳过
    IMMEDIATE_ENABLED: bool = True  # 关闭后只有 Batch/Digest
    EMAIL_ENABLED: bool = True  # 关闭后只站内通知

    # Budget Control
    DAILY_USD_BUDGET: float = 0.33
    EMBED_PER_DAY: int = 500
    EMBED_PER_MIN: int = 300  # 嵌入/分钟上限
    JUDGE_PER_DAY: int = 200

    # Ingest Settings
    NEWSNOW_FETCH_INTERVAL_SEC: int = 1800  # 30 minutes
    RSS_FETCH_INTERVAL_SEC: int = 900  # 15 minutes
    SITE_FETCH_INTERVAL_SEC: int = 1800  # 30 minutes
    ITEMS_PER_SOURCE_PER_FETCH: int = 20
    INGEST_SOURCES_PER_MIN: int = 60
    INGEST_ERROR_BACKOFF_BASE: int = 60  # 错误退避基础秒数
    INGEST_ERROR_BACKOFF_MAX: int = 3600  # 错误退避最大秒数（1小时）
    INGEST_MAX_ERROR_STREAK: int = 5  # 连续错误次数阈值告警

    # Push Settings
    IMMEDIATE_COALESCE_MINUTES: int = 5
    IMMEDIATE_MAX_ITEMS: int = 3
    BATCH_MAX_ITEMS: int = 8
    DIGEST_MAX_ITEMS_PER_GOAL: int = 10
    DIGEST_SEND_HOUR: int = 9  # 09:00 CST
    IMMEDIATE_THRESHOLD: float = 0.93
    BATCH_THRESHOLD: float = 0.75
    DIGEST_MIN_SCORE: float = 0.60
    BOUNDARY_LOW: float = 0.88  # LLM判别边界区间下限
    BOUNDARY_HIGH: float = 0.93  # LLM判别边界区间上限

    # Celery Settings
    CELERY_BROKER_URL: str | None = None  # 默认使用 REDIS_URL
    CELERY_RESULT_BACKEND: str | None = None  # 默认使用 REDIS_URL
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list[str] = ["json"]
    CELERY_TASK_DEFAULT_RETRY_DELAY: int = 60
    CELERY_TASK_MAX_RETRIES: int = 3

    # Worker Concurrency（2c4g 推荐配置）
    WORKER_INGEST_CONCURRENCY: int = 2
    WORKER_EMBED_CONCURRENCY: int = 1
    WORKER_MATCH_CONCURRENCY: int = 1
    WORKER_AGENT_CONCURRENCY: int = 1
    WORKER_EMAIL_CONCURRENCY: int = 1

    @computed_field
    @property
    def celery_broker_url(self) -> str:
        """获取 Celery Broker URL，默认使用 Redis URL。"""
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @computed_field
    @property
    def celery_result_backend(self) -> str:
        """获取 Celery Result Backend URL，默认使用 Redis URL。"""
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        return self


settings = Settings()
