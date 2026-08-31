from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Video Lecture Note Generator"
    api_prefix: str = "/api"
    backend_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    database_url: str = "sqlite:///./storage/app.db"
    storage_path: Path = Path("./storage")
    llm_provider: str = "mock"
    stt_provider: str = "mock"
    vision_provider: str = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    gemini_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    max_upload_size_mb: int = 2048
    key_moment_threshold: int = Field(default=7, ge=1, le=10)
    frame_capture_offset: int = 3
    frame_capture_count: int = 5
    frame_hash_distance_threshold: int = 8
    pdf_provider: str = "playwright"

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
