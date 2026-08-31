from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas.pipeline import TranscriptData


class TranscriptionProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path, duration: float) -> TranscriptData:
        raise NotImplementedError
