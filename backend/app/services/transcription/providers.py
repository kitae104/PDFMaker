from app.core.config import settings
from app.services.transcription.base import TranscriptionProvider
from app.services.transcription.mock import MockTranscriptionProvider


def get_transcription_provider() -> TranscriptionProvider:
    if settings.stt_provider.lower() == "mock":
        return MockTranscriptionProvider()
    return MockTranscriptionProvider()
