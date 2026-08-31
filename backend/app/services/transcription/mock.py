from pathlib import Path

from app.schemas.pipeline import TranscriptData, TranscriptSegment
from app.services.transcription.base import TranscriptionProvider


class MockTranscriptionProvider(TranscriptionProvider):
    def transcribe(self, audio_path: Path, duration: float) -> TranscriptData:
        effective_duration = max(duration or 0, 300)
        topics = [
            "오늘은 영상의 핵심 주제와 전체 학습 흐름을 살펴봅니다.",
            "첫 번째 개념은 문제 배경과 주요 용어를 이해하는 것입니다.",
            "다음으로 실제 예시를 통해 핵심 원리가 어떻게 적용되는지 확인합니다.",
            "중요한 장면에서는 도표와 화면 구성을 바탕으로 관계를 정리합니다.",
            "마지막으로 배운 내용을 요약하고 복습 질문으로 이해도를 점검합니다.",
        ]
        step = effective_duration / len(topics)
        segments = [
            TranscriptSegment(start=round(index * step, 2), end=round((index + 1) * step, 2), text=text)
            for index, text in enumerate(topics)
        ]
        return TranscriptData(language="ko", duration=effective_duration, segments=segments)
