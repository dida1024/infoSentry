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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    MAGIC_LINK_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_TOKEN_BYTES: int = 64
    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_PATH: str = "/"
    REFRESH_COOKIE_DOMAIN: str | None = None
    REFRESH_COOKIE_SECURE: bool = False
    REFRESH_COOKIE_HTTPONLY: bool = True
    REFRESH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    REFRESH_STRICT_IP: bool = True
    REFRESH_STRICT_UA: bool = True
    TRUST_PROXY_HEADERS: bool = False
    FRONTEND_HOST: str = "http://localhost:3000"
    BACKEND_HOST: str = "http://localhost:8000"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    LOG_LEVEL: str = "INFO"
    JWT_ALGORITHM: str = "HS256"
    TIMEZONE: str = "Asia/Shanghai"
    DEFAULT_PAGE: int = 1
    DEFAULT_PAGE_SIZE: int = 20
    SOURCES_PAGE_SIZE: int = 50
    CURSOR_DEFAULT_PAGE: int = 1
    CURSOR_DEFAULT_PAGE_SIZE: int = 20
    NOTIFICATION_GOAL_LOOKUP_LIMIT: int = 100
    MATCH_ITEMS_HOURS_BACK_DEFAULT: int = 24
    MATCH_ITEMS_RECENT_PAGE_SIZE: int = 500
    GOAL_MATCH_RANK_HALF_LIFE_DAYS: float = 14.0
    MATCH_FEEDBACK_PAGE_SIZE: int = 100
    FORCE_INGEST_PAGE_SIZE: int = 1000
    AGENT_HISTORY_PAGE_SIZE: int = 20
    AGENT_RECENT_CLICKS_LIMIT: int = 10
    REDIS_CLIENT_TIMEOUT_SEC: float = 5.0

    # API Key Settings
    API_KEY_MAX_PER_USER: int = 10
    API_KEY_DEFAULT_EXPIRE_DAYS: int = 0  # 0 = no expiry by default

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []
    CORS_ALLOW_METHODS: list[str] = [
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ]
    CORS_ALLOW_HEADERS: list[str] = [
        "Authorization",
        "Content-Type",
        "Accept",
        "X-Requested-With",
        "X-API-Key",
    ]

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

    @model_validator(mode="after")
    def _validate_security_settings(self) -> Self:
        insecure_keys = {
            "",
            "changethis",
            "dev-secret-key-please-change-in-production",
        }
        cors_origins = (
            self.BACKEND_CORS_ORIGINS
            if isinstance(self.BACKEND_CORS_ORIGINS, list)
            else [self.BACKEND_CORS_ORIGINS]
        )
        if "*" in cors_origins:
            raise ValueError("CORS origin '*' is not allowed")
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY in insecure_keys or len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be set and at least 32 characters")
            if not self.REFRESH_COOKIE_SECURE:
                raise ValueError(
                    "REFRESH_COOKIE_SECURE must be True in production environment"
                )
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

    # Prompts (file-based prompt assets)
    PROMPTS_ENABLED: bool = True
    PROMPTS_DIR: str = "prompts"
    PROMPTS_DEFAULT_LANGUAGE: str = "zh-CN"

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
    INGEST_LOCK_TTL_SEC: int = 600  # 抓取任务锁过期时间（10 分钟）

    # Push Settings
    IMMEDIATE_COALESCE_MINUTES: int = 5
    IMMEDIATE_MAX_ITEMS: int = 3
    BATCH_MAX_ITEMS: int = 8
    BATCH_IGNORE_LIMIT: int | None = (
        None  # 若为 None 视为与 BATCH_MAX_ITEMS 相同（总处理上限）
    )
    DIGEST_MAX_ITEMS_PER_GOAL: int = 10
    DIGEST_SEND_HOUR: int = 9  # 09:00 CST
    IMMEDIATE_THRESHOLD: float = 0.89
    BATCH_THRESHOLD: float = 0.75
    DIGEST_MIN_SCORE: float = 0.60
    MATCH_SINGLE_TERM_MIN_COSINE: float = 0.72
    MATCH_SINGLE_TERM_CAP_SCORE: float = 0.599
    BOUNDARY_LOW: float = 0.88  # LLM判别边界区间下限
    BOUNDARY_HIGH: float = 0.93  # LLM判别边界区间上限

    # Goal Email Rate Limiting
    GOAL_EMAIL_RATE_LIMIT_PER_HOUR: int = 5  # 每目标每小时最多发送次数
    GOAL_EMAIL_LOOKBACK_HOURS: int = 24  # 默认回溯小时数
    GOAL_EMAIL_RATE_LIMIT_TTL: int = 3600  # 限流 Redis TTL (秒)
    GOAL_MATCH_RANK_HALF_LIFE_DAYS: float = 14.0  # 目标匹配综合排序半衰期

    # Default Push Windows (HH:MM 格式，逗号分隔)
    DEFAULT_BATCH_WINDOWS: str = "12:30,18:30"
    DEFAULT_DIGEST_SEND_TIME: str = "09:00"

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

    # Fetcher Settings
    FETCHER_TIMEOUT_SEC: float = 30.0  # HTTP 请求超时
    FETCHER_USER_AGENT: str = (
        "Mozilla/5.0 (compatible; InfoSentry/1.0; +https://infosentry.app)"
    )
    # RSSHub 配置 - 支持 rsshub:// 协议的 URL 转换
    RSSHUB_BASE_URL: str = "https://rsshub.app"  # 默认使用官方实例，可配置私有实例

    # Embedding Settings
    EMBED_MAX_CHARS: int = 8000  # 约 2000 tokens

    # API Pricing (USD per 1K tokens) - 用于预算估算
    EMBED_PRICE_PER_1K: float = 0.00002  # text-embedding-3-small
    JUDGE_PRICE_PER_1K: float = 0.00015  # gpt-4o-mini

    # Monitoring Thresholds
    QUEUE_BACKLOG_WARNING: int = 50  # 队列积压警告阈值
    QUEUE_BACKLOG_CRITICAL: int = 100  # 队列积压严重阈值
    LLM_ERROR_RATE_WARNING: int = 5  # LLM 错误率警告阈值（每小时）
    LLM_ERROR_RATE_CRITICAL: int = 10  # LLM 错误率严重阈值（每小时）
    SMTP_ERROR_STREAK_WARNING: int = 2  # SMTP 连续失败警告阈值
    SMTP_ERROR_STREAK_CRITICAL: int = 3  # SMTP 连续失败严重阈值
    WORKER_HEARTBEAT_STALE_SEC: int = 120  # Worker 心跳过期秒数
    WORKER_HEARTBEAT_TTL_SEC: int = 300  # Worker 心跳 Redis TTL

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
