from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_base_url: AnyHttpUrl = Field(default="http://127.0.0.1:8000", alias="APP_BASE_URL")

    session_secret: str = Field(default="change-me", alias="SESSION_SECRET")

    database_url: str = Field(default="sqlite:///./data/app.db", alias="DATABASE_URL")

    openai_base_url: AnyHttpUrl = Field(default="https://ai.example.com/v1", alias="OPENAI_BASE_URL")
    openai_api_key: str = Field(default="sk-change-me", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="Qwen/Qwen3-32B", alias="OPENAI_MODEL")

    model_timeout_seconds: int = Field(default=180, alias="MODEL_TIMEOUT_SECONDS")
    model_temperature: float = Field(default=0.4, alias="MODEL_TEMPERATURE")
    model_top_p: float = Field(default=0.8, alias="MODEL_TOP_P")
    model_max_tokens: int = Field(default=2500, alias="MODEL_MAX_TOKENS")

    max_input_chars: int = Field(default=5000, alias="MAX_INPUT_CHARS")
    max_upload_size_mb: int = Field(default=5, alias="MAX_UPLOAD_SIZE_MB")
    max_concurrent_generations: int = Field(default=2, alias="MAX_CONCURRENT_GENERATIONS")

    secure_cookies: bool = Field(default=False, alias="SECURE_COOKIES")


@lru_cache
def get_settings() -> Settings:
    return Settings()
