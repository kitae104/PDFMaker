from app.core.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.mock import MockLLMProvider


def get_llm_provider() -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider in {"mock", "openai", "gemini", "ollama"}:
        return MockLLMProvider()
    return MockLLMProvider()
