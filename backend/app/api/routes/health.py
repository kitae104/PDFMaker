import logging
from time import perf_counter

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.jobs import HealthResponse, LLMHealthResponse
from app.services.llm.openai import classify_llm_error
from app.services.llm.providers import effective_llm_model, effective_llm_provider_name, get_llm_provider
from app.services.transcription.mock import MockTranscriptionProvider
from app.services.transcription.providers import get_transcription_provider

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


def effective_stt_provider_name() -> str:
    if isinstance(get_transcription_provider(), MockTranscriptionProvider):
        return "mock"
    return settings.stt_provider.lower()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db_kind = "sqlite" if settings.database_url.startswith("sqlite") else "postgresql"
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        database=db_kind,
        llm_provider=effective_llm_provider_name(),
        llm_model=effective_llm_model(),
        stt_provider=effective_stt_provider_name(),
    )


@router.get("/health/llm", response_model=LLMHealthResponse)
def llm_health() -> LLMHealthResponse:
    provider_name = effective_llm_provider_name()
    model = effective_llm_model()
    if provider_name == "mock":
        return LLMHealthResponse(ok=True, provider="mock", model=None, latency_ms=None, error=None)
    started = perf_counter()
    try:
        provider = get_llm_provider()
        provider.ping()
    except Exception as exc:
        latency_ms = int((perf_counter() - started) * 1000)
        # Only the exception type is logged: messages may contain request URLs.
        logger.warning("LLM health check failed for %s: %s", provider_name, type(exc).__name__)
        return LLMHealthResponse(ok=False, provider=provider_name, model=model, latency_ms=latency_ms, error=classify_llm_error(exc))
    latency_ms = int((perf_counter() - started) * 1000)
    return LLMHealthResponse(ok=True, provider=provider_name, model=model, latency_ms=latency_ms, error=None)
