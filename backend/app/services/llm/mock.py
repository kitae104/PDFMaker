import re

from app.schemas.jobs import GenerationOptions
from app.schemas.pipeline import (
    ChapterAnalysis,
    ChapterData,
    KeyMomentAnalysis,
    KeyMomentData,
    LessonChapter,
    LessonContent,
    TranscriptData,
)
from app.services.llm.base import LLMProvider
from app.services.video import format_timestamp


class MockLLMProvider(LLMProvider):
    def analyze_transcript(self, transcript: TranscriptData) -> dict:
        return {"language": transcript.language, "segment_count": len(transcript.segments), "duration": transcript.duration}

    def generate_chapters(self, transcript: TranscriptData) -> ChapterAnalysis:
        duration = max(transcript.duration, 300)
        chapter_count = 5 if duration >= 900 or len(transcript.segments) >= 80 else 3
        size = duration / chapter_count
        chapters = []
        for index in range(chapter_count):
            start = round(index * size, 2)
            end = round((index + 1) * size, 2)
            segments = segments_between(transcript, start, end)
            title = make_title(segments, fallback=f"Chapter {index + 1}")
            summary = make_summary(segments, fallback=f"{title} 구간에서 영상의 주요 설명을 학습 흐름에 맞게 정리합니다.")
            chapters.append(
                ChapterData(
                    title=title,
                    start=start,
                    end=end,
                    summary=summary,
                    importance=8 + (index % 2),
                )
            )
        return ChapterAnalysis(chapters=chapters)

    def select_key_moments(self, transcript: TranscriptData, chapters: ChapterAnalysis) -> KeyMomentAnalysis:
        moments: list[KeyMomentData] = []
        for chapter in chapters.chapters:
            chapter_segments = segments_between(transcript, chapter.start, chapter.end)
            key_segment = max(chapter_segments, key=lambda segment: len(segment.text), default=None)
            timestamp = key_segment.start if key_segment else chapter.start + (chapter.end - chapter.start) / 2
            moments.append(
                KeyMomentData(
                    timestamp=round(timestamp, 2),
                    title=f"{chapter.title} 핵심 화면",
                    reason="Transcript에서 설명량이 많고 Chapter의 핵심 개념을 대표하는 지점입니다.",
                    importance=9,
                    captureRecommended=True,
                )
            )
        if chapters.chapters:
            first = chapters.chapters[0]
            moments.append(
                KeyMomentData(
                    timestamp=round(first.start + 12, 2),
                    title="도입부 학습 목표",
                    reason="강의 전체 방향을 이해하는 데 도움이 되는 장면입니다.",
                    importance=7,
                    captureRecommended=True,
                )
            )
        return KeyMomentAnalysis(keyMoments=moments[:5])

    def generate_lesson_content(
        self,
        transcript: TranscriptData,
        chapters: ChapterAnalysis,
        moments: KeyMomentAnalysis,
        options: GenerationOptions,
    ) -> LessonContent:
        lesson_chapters: list[LessonChapter] = []
        for index, chapter in enumerate(chapters.chapters, start=1):
            chapter_segments = segments_between(transcript, chapter.start, chapter.end)
            excerpt = make_summary(chapter_segments, max_chars=520, fallback=chapter.summary)
            key_points = make_key_points(chapter_segments)
            lesson_chapters.append(
                LessonChapter(
                    title=f"{index}. {chapter.title}",
                    learning_objectives=[f"{chapter.title}의 핵심 개념을 설명할 수 있다."],
                    explanation=(
                        "이 장은 Transcript에서 확인되는 설명을 중심으로 구성되었습니다. "
                        f"주요 흐름은 다음과 같습니다. {excerpt}"
                    ),
                    beginner_explanation=f"쉽게 말하면, 이 구간은 '{chapter.title}'을 실제 영상 설명 순서대로 따라가며 이해하는 부분입니다.",
                    key_points=key_points,
                    terms=[
                        {"term": term, "definition": "Transcript에서 반복적으로 등장하거나 이 Chapter를 대표하는 핵심 표현입니다."}
                        for term in extract_terms(chapter_segments)[:4]
                    ],
                    timestamp=format_timestamp(chapter.start),
                    summary=f"{chapter.title}은 전체 내용을 이해하기 위한 중요한 학습 단위입니다.",
                )
            )
        return LessonContent(
            title="AI Generated Lecture Notes",
            overview=self.summarize(transcript),
            learning_objectives=["영상의 핵심 흐름을 파악한다.", "중요 장면과 개념을 연결해 복습한다."],
            chapters=lesson_chapters,
            final_summary=["영상 내용은 단계별 개념 이해와 복습에 적합하게 정리되었습니다.", "Timestamp를 활용하면 원본 장면으로 빠르게 돌아갈 수 있습니다."],
            review_questions=["이 영상에서 가장 중요한 개념은 무엇인가요?", "각 Chapter의 핵심 장면은 어떤 설명과 연결되나요?"],
        )

    def generate_lesson_from_scene_windows(
        self,
        title: str,
        transcript: TranscriptData,
        windows: list[dict],
        options: GenerationOptions,
    ) -> LessonContent:
        lesson_chapters: list[LessonChapter] = []
        for index, window in enumerate(windows, start=1):
            segments = window.get("segments", [])
            chapter_title = window.get("title") or make_title(segments, fallback=f"Scene {index}")
            excerpt = make_summary(segments, max_chars=700, fallback=window.get("summary", ""))
            lesson_chapters.append(
                LessonChapter(
                    title=f"{index}. {chapter_title}",
                    learning_objectives=[f"{chapter_title} 구간의 핵심 내용을 설명할 수 있다."],
                    explanation=f"선택된 이미지 이후 다음 선택 이미지 전까지의 스크립트를 통합해 정리했습니다. {excerpt}",
                    beginner_explanation=f"쉽게 말하면, 이 부분은 '{chapter_title}' 장면에서 시작된 설명을 하나의 학습 단위로 묶은 것입니다.",
                    key_points=make_key_points(segments),
                    terms=[
                        {"term": term, "definition": "이 이미지 구간의 스크립트에서 반복되거나 핵심적으로 등장한 표현입니다."}
                        for term in extract_terms(segments)[:4]
                    ],
                    timestamp=format_timestamp(float(window.get("start", 0))),
                    summary=make_summary(segments, max_chars=160, fallback=f"{chapter_title} 구간 요약"),
                )
            )
        return LessonContent(
            title=title or "AI Generated Lecture Notes",
            overview=self.summarize(transcript),
            learning_objectives=["장면 변화 지점을 기준으로 영상의 전체 흐름을 빠짐없이 이해한다.", "선택된 이미지와 연결된 스크립트 구간을 학습 단위로 정리한다."],
            chapters=lesson_chapters,
            final_summary=["선택된 이미지 기준 구간들이 영상 Transcript 전체를 순서대로 커버하도록 구성되었습니다.", "각 구간은 다음 선택 이미지 전까지의 설명을 통합해 정리했습니다."],
            review_questions=["각 이미지가 나타내는 핵심 개념은 무엇인가요?", "이미지 사이의 스크립트 흐름에서 반드시 기억해야 할 내용은 무엇인가요?"],
        )

    def summarize(self, transcript: TranscriptData) -> str:
        sample = make_summary(transcript.segments[:24], max_chars=260, fallback="Transcript 내용이 충분하지 않습니다.")
        return f"이 자료는 영상 Transcript를 바탕으로 핵심 내용을 교육용 노트 형태로 재구성합니다. {sample}"


def segments_between(transcript: TranscriptData, start: float, end: float):
    return [segment for segment in transcript.segments if segment.end >= start and segment.start <= end and segment.text.strip()]


def make_title(segments, fallback: str) -> str:
    for segment in segments:
        text = normalize_text(segment.text)
        if len(text) >= 8:
            words = text.split()
            return " ".join(words[:8]).rstrip(".,!?")[:80]
    return fallback


def make_summary(segments, max_chars: int = 300, fallback: str = "") -> str:
    texts = [normalize_text(segment.text) for segment in segments if normalize_text(segment.text)]
    if not texts:
        return fallback
    summary = " ".join(texts[:8])
    return summary[:max_chars].rstrip()


def make_key_points(segments) -> list[str]:
    points = []
    for segment in segments[:12]:
        text = normalize_text(segment.text)
        if len(text) >= 10:
            points.append(text[:90].rstrip())
        if len(points) == 4:
            break
    return points or ["Transcript 기반 핵심 흐름 확인", "Timestamp 기반 복습"]


def extract_terms(segments) -> list[str]:
    text = " ".join(normalize_text(segment.text) for segment in segments)
    tokens = re.findall(r"[A-Za-z가-힣0-9]{2,}", text)
    stopwords = {"그리고", "그러면", "이렇게", "저렇게", "것입니다", "있습니다", "합니다", "오늘은", "영상에서"}
    counts: dict[str, int] = {}
    for token in tokens:
        if token in stopwords:
            continue
        counts[token] = counts.get(token, 0) + 1
    terms = sorted(counts, key=lambda token: (-counts[token], token))
    return terms or ["Transcript", "Key Moment"]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
