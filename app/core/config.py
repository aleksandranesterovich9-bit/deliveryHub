from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables and the `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DeliveryHub"
    log_level: str = "INFO"

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    secret_key: SecretStr
    access_token_expire_minutes: int = 30

    cache_ttl_seconds: int = 60
    login_max_attempts: int = 5
    login_block_seconds: int = 15 * 60

    outbox_poll_interval_seconds: float = 1.0
    outbox_batch_size: int = 100

    # Optional: the seed script creates an admin with these credentials.
    admin_phone: str | None = None
    admin_password: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def use_async_driver(cls, value: str) -> str:
        # Allow the plain `postgresql://` form, but always talk to Postgres via asyncpg.
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
