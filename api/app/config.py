from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://postgres:dev@localhost:5432/health"
    API_KEY: str = "change-me"
    SERVER_SECRET: str = "dev-secret-key-32-chars-long-abc123!"
    DEV_CORS: bool = False
    STORAGE_PATH: str = "/data/files"
    STATIC_DIR: str = "/app/static"

    # Optional Headless/CI fallback environment variables
    LLM_BASE_URL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None


@lru_cache()
def get_settings() -> Settings:
    return Settings()
