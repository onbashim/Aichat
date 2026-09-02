from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str | None = None

    telegram_bot_token: str | None = None
    telegram_owner_id: int | None = None
    telegram_webhook_secret: str | None = None
    telegram_webhook_url: str | None = None
    railway_public_domain: str | None = None

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-terra"
    openai_timeout_seconds: float = 30.0
    openai_max_retries: int = 2

    ai_automation_enabled: bool = False
    autopilot_enabled: bool = False

    ai_rate_limit_requests: int = 30
    ai_rate_limit_window_seconds: int = 60
    owner_rate_limit_requests: int = 60
    owner_rate_limit_window_seconds: int = 60

    app_name: str = "Telegram AI OS"
    app_version: str = "0.1.0"

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value[len("postgres://") :]
        if value.startswith("postgresql://") and "+asyncpg" not in value:
            return "postgresql+asyncpg://" + value[len("postgresql://") :]
        return value

    @property
    def webhook_url(self) -> str | None:
        if self.telegram_webhook_url:
            return self.telegram_webhook_url.rstrip("/")
        if self.railway_public_domain:
            return f"https://{self.railway_public_domain.rstrip('/')}/telegram/webhook"
        return None

    @property
    def runtime_ready(self) -> bool:
        return bool(
            self.telegram_bot_token
            and self.telegram_owner_id
            and self.telegram_webhook_secret
            and self.openai_api_key
            and self.database_url
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
