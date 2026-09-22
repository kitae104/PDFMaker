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
            # 값이 있을 때만 payload에 reasoning_effort로 실린다 (thinking 토큰이 max_tokens를 잠식하는 것을 줄이는 용도).
            reasoning_effort=getattr(settings, "gemini_reasoning_effort", None),
        )
