from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./integration_hub.db"
    frontend_origin: str = "http://127.0.0.1:5173"
    operator_username: str = "operator"
    operator_password: str = "local-development-only"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
