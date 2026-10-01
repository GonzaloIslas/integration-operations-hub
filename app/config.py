from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    application_name: str = "integration-operations-hub"
    application_environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./integration_hub.db"
    frontend_origin: str = "http://127.0.0.1:5173"
    operator_username: str = "operator"
    operator_password: str = "local-development-only"
    integration_api_key: str = "local-integration-api-key"
    api_rate_limit: int = 100
    api_rate_window_seconds: int = 60
    provider_timeout_ms: int = 2_000
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/%2F"
    retry_max_attempts: int = 3
    retry_initial_backoff_seconds: int = 5
    openai_api_key: str | None = None
    openai_model: str = "gpt-6-astra"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
