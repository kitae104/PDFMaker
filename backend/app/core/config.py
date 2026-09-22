import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ (contains app/) and repository root. Paths below are resolved against these
# so the app behaves the same regardless of the current working directory.
BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent

_SQLITE_URL_RE = re.compile(r"^(sqlite(?:\+\w+)?):///(.*)$")


def resolve_backend_path(value: Path | str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path.resolve()


def resolve_sqlite_url(url: str) -> str:
    match = _SQLITE_URL_RE.match(url)
    if not match:
        return url
    scheme, rest = match.groups()
    path_part, sep, query = rest.partition("?")
    if not path_part or path_part == ":memory:" or path_part.startswith("file:"):
        return url
    if Path(path_part).is_absolute() or path_part.startswith("/"):
        return url
    absolute = resolve_backend_path(path_part).as_posix()
    return f"{scheme}:///{absolute}{sep}{query}"


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
    gemini_model: str = "gemini-3.7-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_reasoning_effort: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    llm_timeout_seconds: float = 120
    llm_max_retries: int = Field(default=3, ge=0)
    llm_use_system_trust_store: bool = True
    llm_ca_bundle: str | None = None
    transcript_correction_profile: str = "auto"
    max_upload_size_mb: int = 2048
    key_moment_threshold: int = Field(default=7, ge=1, le=10)
    frame_capture_offset: int = 3
    frame_capture_count: int = 5
    frame_hash_distance_threshold: int = 8
    scene_review_interval_seconds: int = Field(default=25, ge=5)
    scene_review_min_scenes: int = Field(default=12, ge=1)
    scene_review_max_scenes: int = Field(default=120, ge=1)
    pdf_provider: str = "playwright"

    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        self.storage_path = resolve_backend_path(self.storage_path)
        self.database_url = resolve_sqlite_url(self.database_url)
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
