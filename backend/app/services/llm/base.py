from abc import ABC, abstractmethod

from app.schemas.jobs import GenerationOptions
from app.schemas.pipeline import ChapterAnalysis, KeyMomentAnalysis, LessonContent, TranscriptData


class LLMProvider(ABC):
    @abstractmethod
    def analyze_transcript(self, transcript: TranscriptData) -> dict:
        raise NotImplementedError

    @abstractmethod
    def generate_chapters(self, transcript: TranscriptData) -> ChapterAnalysis:
        raise NotImplementedError

    @abstractmethod
    def select_key_moments(self, transcript: TranscriptData, chapters: ChapterAnalysis) -> KeyMomentAnalysis:
        raise NotImplementedError

    @abstractmethod
    def generate_lesson_content(
        self,
        transcript: TranscriptData,
        chapters: ChapterAnalysis,
        moments: KeyMomentAnalysis,
        options: GenerationOptions,
    ) -> LessonContent:
        raise NotImplementedError

    @abstractmethod
    def generate_lesson_from_scene_windows(
        self,
        title: str,
        transcript: TranscriptData,
        windows: list[dict],
        options: GenerationOptions,
    ) -> LessonContent:
        raise NotImplementedError

    @abstractmethod
    def summarize(self, transcript: TranscriptData) -> str:
        raise NotImplementedError
