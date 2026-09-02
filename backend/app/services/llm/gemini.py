from app.core.config import settings
from app.services.llm.openai import OpenAILLMProvider


class GeminiLLMProvider(OpenAILLMProvider):
    def __init__(self) -> None:
        super().__init__(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            base_url=settings.gemini_base_url,
            provider_label="Gemini",
            api_key_name="GEMINI_API_KEY",
        )
