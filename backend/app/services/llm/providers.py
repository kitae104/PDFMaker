from app.core.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.gemini import GeminiLLMProvider
from app.services.llm.mock import MockLLMProvider
from app.services.llm.openai import OpenAILLMProvider


def get_llm_provider() -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider == "openai" and settings.openai_api_key:
        return OpenAILLMProvider()
    if provider == "openai":
        return MockLLMProvider()
    if provider == "gemini" and settings.gemini_api_key:
        return GeminiLLMProvider()
    if provider == "gemini":
        return MockLLMProvider()
    if provider in {"mock", "ollama"}:
        return MockLLMProvider()
    return MockLLMProvider()
