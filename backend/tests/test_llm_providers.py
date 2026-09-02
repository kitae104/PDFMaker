from app.services.llm.gemini import GeminiLLMProvider
from app.services.llm.mock import MockLLMProvider
from app.services.llm.openai import OpenAILLMProvider
from app.services.llm.providers import get_llm_provider


def test_get_llm_provider_returns_openai_when_key_is_configured(monkeypatch):
    monkeypatch.setattr("app.services.llm.providers.settings.llm_provider", "openai")
    monkeypatch.setattr("app.services.llm.providers.settings.openai_api_key", "test-openai-key")

    provider = get_llm_provider()

    assert isinstance(provider, OpenAILLMProvider)
    assert provider.api_key == "test-openai-key"


def test_get_llm_provider_returns_gemini_when_key_is_configured(monkeypatch):
    monkeypatch.setattr("app.services.llm.providers.settings.llm_provider", "gemini")
    monkeypatch.setattr("app.services.llm.providers.settings.gemini_api_key", "test-gemini-key")
    monkeypatch.setattr("app.services.llm.providers.settings.gemini_model", "gemini-test-model")

    provider = get_llm_provider()

    assert isinstance(provider, GeminiLLMProvider)
    assert provider.api_key == "test-gemini-key"
    assert provider.model == "gemini-test-model"


def test_get_llm_provider_falls_back_to_mock_when_selected_key_is_missing(monkeypatch):
    monkeypatch.setattr("app.services.llm.providers.settings.llm_provider", "gemini")
    monkeypatch.setattr("app.services.llm.providers.settings.gemini_api_key", "")

    assert isinstance(get_llm_provider(), MockLLMProvider)


def test_gemini_provider_requires_gemini_key_even_when_openai_key_exists(monkeypatch):
    monkeypatch.setattr("app.services.llm.gemini.settings.gemini_api_key", "")
    monkeypatch.setattr("app.services.llm.gemini.settings.openai_api_key", "test-openai-key")

    try:
        GeminiLLMProvider()
    except RuntimeError as exc:
        assert "GEMINI_API_KEY" in str(exc)
    else:
        raise AssertionError("GeminiLLMProvider should require GEMINI_API_KEY")
