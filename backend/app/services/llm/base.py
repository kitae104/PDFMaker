from abc import ABC, abstractmethod

from app.schemas.jobs import GenerationOptions
from app.schemas.pipeline import ChapterAnalysis, KeyMomentAnalysis, LessonContent, SceneWindowSummaryList, TranscriptData


class LLMProvider(ABC):
    def drain_fallback_warnings(self) -> list[str]:
        """이번 호출들에서 쌓인 사용자용 폴백 경고를 반환하고 비운다. 기록이 없으면 []."""
        warnings = getattr(self, "_fallback_warnings", None)
        if not warnings:
            return []
        drained = list(warnings)
        warnings.clear()
        return drained

    def _record_fallback_warning(self, message: str) -> None:
        warnings = getattr(self, "_fallback_warnings", None)
        if warnings is None:
            warnings = []
            self._fallback_warnings = warnings
        if message not in warnings:
            warnings.append(message)

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
    def summarize_scene_windows(self, windows: list[dict]) -> SceneWindowSummaryList:
        raise NotImplementedError

    @abstractmethod
    def summarize(self, transcript: TranscriptData) -> str:
        raise NotImplementedError
