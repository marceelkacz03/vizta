from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VIZTA"
    base_url: str = "http://127.0.0.1:8000"
    session_secret: str = "vizta-local-dev-secret"
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def supabase_key(self) -> str | None:
        return self.supabase_anon_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
