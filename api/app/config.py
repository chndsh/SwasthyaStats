from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://postgres:dev@localhost:5432/health"
    API_KEY: Optional[str] = "change-me"
    SERVER_SECRET: str = "dev-secret-key-32-chars-long-abc123!"
    DEV_CORS: bool = False
    STORAGE_PATH: str = "/data/files"
    STATIC_DIR: str = "/app/static"

    ADMIN_EMAIL: str = "admin@localhost"
    ADMIN_PASSWORD: str = "adminpass"

    # Optional Headless/CI fallback environment variables
    LLM_BASE_URL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    @field_validator("SERVER_SECRET")
    @classmethod
    def validate_server_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SERVER_SECRET must be at least 32 characters long.")
        return v


@lru_cache()
def get_settings() -> Settings:
    return Settings()
